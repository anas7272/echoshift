"""RELAY backend.

This server serves the browser app, issues scoped token access for AssemblyAI,
and runs a generic support-session state model designed for interruption, context updates,
escalation, and human handoff without payment or e-commerce logic.
"""

from __future__ import annotations

import base64
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import base64
import os
import tempfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List

import httpx
import pyttsx3
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.providers import generate_provider_reply, provider_status

BASE_DIR = Path(__file__).resolve().parent
for env_file in (BASE_DIR / ".env", BASE_DIR / "env" / ".env"):
    if env_file.exists():
        load_dotenv(env_file)

API_KEY = os.getenv("ASSEMBLYAI_API_KEY") or os.getenv("ASSEMBLYAI_KEY")
if not API_KEY:
    print("WARNING: ASSEMBLYAI_API_KEY is not set. Create a .env file at the workspace root or in /env/.env.")

app = FastAPI(title="RELAY — Interruptible Voice AI Agent")
STATIC_DIR = BASE_DIR / "static"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


SESSION_STATE: Dict[str, Any] = {
    "session_id": "demo-session-001",
    "customer_name": "",
    "language": "hinglish",
    "current_intent": "support_help_request",
    "current_issue": "",
    "conversation_summary": "",
    "important_facts": [],
    "recent_user_message": "",
    "recent_ai_message": "",
    "actions_taken": [
        "acknowledge_issue",
        "request_details",
        "track_context",
    ],
    "interruption_count": 0,
    "escalation_requested": False,
    "escalation_reason": None,
    "status": "LISTENING",
    "human_status": "AWAITING_HUMAN",
    "recent_conversation": [],
    "handoff": None,
}

TRACE_EVENTS: List[Dict[str, Any]] = [
    {"type": "agent_state", "state": "LISTENING", "timestamp": now_iso(), "metadata": {"message": "Session initialized."}},
]


def append_event(event_type: str, **payload: Any) -> None:
    TRACE_EVENTS.append({"type": event_type, "timestamp": now_iso(), **payload})


def build_handoff() -> Dict[str, Any]:
    state = SESSION_STATE.copy()
    summary = state.get("conversation_summary") or ""
    return {
        "session_id": state["session_id"],
        "customer_name": state.get("customer_name") or "Customer",
        "language": state.get("language") or "hinglish",
        "intent": state.get("current_intent") or "support_help_request",
        "issue": state.get("current_issue") or "support_issue_pending",
        "summary": summary,
        "important_facts": state.get("important_facts") or [],
        "recent_conversation": state.get("recent_conversation") or [],
        "actions_taken": state.get("actions_taken") or [],
        "escalation_reason": state.get("escalation_reason") or "user_requested_human_support",
        "status": "READY_FOR_TAKEOVER",
        "timestamp": now_iso(),
    }


def build_session_prompt(user_text: str, session: Dict[str, Any] | None = None) -> str:
    state = session or SESSION_STATE
    facts = state.get("important_facts") or []
    recent = state.get("recent_conversation") or []
    summary = state.get("conversation_summary") or "No summary yet."
    relevant_history = "; ".join(
        f"{item.get('role', 'unknown')}: {item.get('text', '')}" for item in recent[-4:]
    )
    fact_text = "; ".join(facts[:5]) if facts else "No important facts recorded."
    return (
        "You are RELAY, a multilingual support AI. "
        f"Customer: {state.get('customer_name') or 'Unknown'} | "
        f"Issue: {state.get('current_issue') or 'Not yet specified'} | "
        f"Language: {state.get('language') or 'english'} | "
        f"Summary: {summary} | "
        f"Important facts: {fact_text} | "
        f"Recent conversation: {relevant_history or 'No previous conversation'} | "
        f"User just said: \"{user_text}\". "
        "Treat this as the latest turn and preserve the current context. "
        "If the user is correcting a previous statement or interrupting the AI, update the issue using the correction and answer based on the corrected fact. "
        "Keep replies short, calm, and useful. If the user asks for a human, escalate."
    )


def text_to_speech_local(text: str) -> str:
    """Generate offline local TTS for the reply using pyttsx3."""
    if not text or not text.strip():
        return ""
    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", 150)
        engine.setProperty("volume", 0.9)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            out_path = tmp.name
        engine.save_to_file(text, out_path)
        engine.runAndWait()
        with open(out_path, "rb") as f:
            payload = f.read()
        os.remove(out_path)
        return payload.hex()
    except Exception:
        return ""


@app.get("/")
async def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok", "service": "RELAY"}


@app.get("/api/provider-status")
async def get_provider_status() -> Dict[str, Any]:
    return provider_status()


@app.post("/api/provider/chat")
async def provider_chat(payload: Dict[str, Any]) -> Dict[str, Any]:
    provider = payload.get("provider", "AssemblyAI Voice")
    user_message = payload.get("message", "")
    reply = generate_provider_reply(provider, user_message, SESSION_STATE)
    return {"provider": provider, "reply": reply, "session": SESSION_STATE}


@app.get("/api/voice-token")
async def get_voice_token() -> Dict[str, str]:
    """Mint a short-lived AssemblyAI voice token without exposing the permanent key."""
    if not API_KEY:
        raise HTTPException(status_code=500, detail="ASSEMBLYAI_API_KEY not configured on server")

    url = "https://agents.assemblyai.com/v1/token"
    params = {"expires_in_seconds": "300"}
    headers = {"Authorization": f"Bearer {API_KEY}"}

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, params=params, headers=headers, timeout=12.0)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"AssemblyAI token request failed: {exc.response.status_code} {exc.response.text}",
            ) from exc
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"Could not reach AssemblyAI: {exc}") from exc

    payload = resp.json()
    token = payload.get("token")
    if not token:
        raise HTTPException(status_code=502, detail="AssemblyAI did not return a token")
    return {"token": token}


@app.get("/api/session")
async def get_session() -> Dict[str, Any]:
    return {"session": SESSION_STATE, "trace": TRACE_EVENTS}


@app.get("/api/relay/session")
async def relay_session() -> Dict[str, Any]:
    return {"session": SESSION_STATE, "trace": TRACE_EVENTS}


@app.get("/api/relay/handoff")
async def relay_handoff() -> Dict[str, Any]:
    return {"handoff": build_handoff() if not SESSION_STATE["handoff"] else SESSION_STATE["handoff"]}


@app.post("/api/relay/escalate")
async def relay_escalate() -> Dict[str, Any]:
    return await session_escalate()


@app.post("/api/relay/takeover")
async def relay_takeover() -> Dict[str, Any]:
    return await session_takeover()


@app.post("/api/session/interruption")
async def session_interruption() -> Dict[str, Any]:
    SESSION_STATE["interruption_count"] += 1
    SESSION_STATE["status"] = "INTERRUPTED"
    SESSION_STATE["actions_taken"].append("context_updated_after_interruption")
    SESSION_STATE["important_facts"].append("User interrupted while AI was responding and clarified the issue.")
    SESSION_STATE["conversation_summary"] = "Customer clarified the account problem after interrupting the AI response; the system should continue from the updated context."
    SESSION_STATE["recent_user_message"] = "Wait, that's not exactly what happened."
    append_event("interruption", message="User interrupted the AI response.", interruption_count=SESSION_STATE["interruption_count"])
    append_event("agent_state", state="CONTEXT_UPDATED", metadata={"message": "Conversation context updated."})
    append_event("agent_state", state="THINKING", metadata={"message": "Agent re-evaluating the issue from updated context."})
    return {"status": "ok", "session": SESSION_STATE}


@app.post("/api/session/escalate")
async def session_escalate(reason: str = Query(default="user_requested_human_support")) -> Dict[str, Any]:
    SESSION_STATE["escalation_requested"] = True
    SESSION_STATE["escalation_reason"] = reason
    SESSION_STATE["status"] = "ESCALATING"
    SESSION_STATE["human_status"] = "READY_FOR_TAKEOVER"
    SESSION_STATE["handoff"] = build_handoff()
    append_event("escalation", reason=reason, message="Escalation requested by customer.")
    append_event("agent_state", state="PREPARING_HANDOFF", metadata={"handoff": SESSION_STATE["handoff"]})
    return {"status": "ok", "handoff": SESSION_STATE["handoff"], "session": SESSION_STATE}


@app.post("/api/session/takeover")
async def session_takeover() -> Dict[str, Any]:
    SESSION_STATE["status"] = "HUMAN_ACTIVE"
    SESSION_STATE["human_status"] = "HUMAN_JOINED"
    append_event("agent_state", state="HUMAN_JOINED", metadata={"message": "Human agent joined and took over the session."})
    return {"status": "ok", "session": SESSION_STATE}


@app.post("/api/session/update")
async def session_update(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Update the live support context from the user conversation."""
    if "customer_name" in payload and payload["customer_name"]:
        SESSION_STATE["customer_name"] = payload["customer_name"]
    if "recent_user_message" in payload and payload["recent_user_message"]:
        SESSION_STATE["recent_user_message"] = payload["recent_user_message"]
    if "recent_ai_message" in payload and payload["recent_ai_message"]:
        SESSION_STATE["recent_ai_message"] = payload["recent_ai_message"]
    if "recent_conversation" in payload:
        SESSION_STATE["recent_conversation"] = payload["recent_conversation"]
    if "important_facts" in payload:
        SESSION_STATE["important_facts"] = payload["important_facts"]
    if "conversation_summary" in payload:
        SESSION_STATE["conversation_summary"] = payload["conversation_summary"]
    if "current_issue" in payload:
        SESSION_STATE["current_issue"] = payload["current_issue"]
    if "current_intent" in payload:
        SESSION_STATE["current_intent"] = payload["current_intent"]
    if "status" in payload:
        SESSION_STATE["status"] = payload["status"]
    if "human_status" in payload:
        SESSION_STATE["human_status"] = payload["human_status"]
    if "escalation_requested" in payload:
        SESSION_STATE["escalation_requested"] = payload["escalation_requested"]
    if "escalation_reason" in payload:
        SESSION_STATE["escalation_reason"] = payload["escalation_reason"]
    for key, value in payload.items():
        if key in SESSION_STATE and key not in {"customer_name", "recent_user_message", "recent_ai_message", "recent_conversation", "important_facts", "conversation_summary", "current_issue", "current_intent", "status", "human_status", "escalation_requested", "escalation_reason"}:
            SESSION_STATE[key] = value
    append_event("session_update", payload=payload)
    return {"status": "ok", "session": SESSION_STATE}


@app.post("/api/voice/transcribe-and-reply")
async def transcribe_and_reply(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Full-duplex voice route: context-aware reply + local TTS for browser playback."""
    user_input = payload.get("user_input") or payload.get("text") or payload.get("transcript") or ""
    audio_payload = payload.get("audio")

    if not user_input and not audio_payload:
        return {"error": "No user input", "session": SESSION_STATE}

    if not user_input:
        user_input = "User speaking..."

    SESSION_STATE["recent_user_message"] = user_input
    SESSION_STATE["status"] = "LISTENING"

    context_facts = "\n".join(SESSION_STATE.get("important_facts", []))
    context_prompt = f"""
You are RELAY, a support agent.
Customer: {SESSION_STATE.get('customer_name', 'Customer')}
Issue: {SESSION_STATE.get('current_issue', 'Not yet specified')}
Language: {SESSION_STATE.get('language', 'english')}
Context facts:
{context_facts}

User just said: "{user_input}"

Respond in 1-2 sentences. If they ask for human support, say you're escalating.
"""

    provider_name = "assemblyai"
    reply = generate_provider_reply(provider_name, context_prompt, SESSION_STATE)

    SESSION_STATE["recent_ai_message"] = reply
    history = SESSION_STATE.get("recent_conversation") or []
    SESSION_STATE["recent_conversation"] = history[-6:] + [
        {"role": "user", "text": user_input},
        {"role": "agent", "text": reply},
    ]

    if any(word in user_input.lower() for word in ["human", "agent", "person", "escalate", "talk to a person"]):
        SESSION_STATE["escalation_requested"] = True
        SESSION_STATE["escalation_reason"] = "user_requested_human_support"
        SESSION_STATE["status"] = "ESCALATING"
        SESSION_STATE["human_status"] = "READY_FOR_TAKEOVER"
        SESSION_STATE["handoff"] = build_handoff()

    if any(word in user_input.lower() for word in ["account", "login", "password", "locked", "blocked", "issue", "problem"]):
        SESSION_STATE["current_issue"] = "account_access_issue"

    audio_b64 = text_to_speech_local(reply)
    append_event("voice_turn", user_input=user_input, ai_reply=reply)

    return {
        "user_input": user_input,
        "reply": reply,
        "audio": audio_b64,
        "session": SESSION_STATE,
        "timestamp": now_iso(),
    }


@app.get("/api/session/handoff")
async def get_handoff() -> Dict[str, Any]:
    handoff = build_handoff() if not SESSION_STATE["handoff"] else SESSION_STATE["handoff"]
    return {"handoff": handoff}


@app.get("/api/session/trace")
async def get_trace() -> Dict[str, Any]:
    return {"trace": TRACE_EVENTS}


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
