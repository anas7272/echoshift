from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List
from urllib import error, request

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
for env_file in (BASE_DIR / ".env", BASE_DIR / "env" / ".env"):
    if env_file.exists():
        load_dotenv(env_file)

ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY") or os.getenv("ASSEMBLYAI_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY") or os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_MODEL = os.getenv("GROQ_MODEL") or os.getenv("GROK_MODEL", "openai/gpt-oss-20b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:1.5b")


def normalize_provider_name(provider_name: str | None) -> str:
    if not provider_name:
        return "assemblyai"
    key = provider_name.lower().replace(" ", "_")
    if "grok" in key:
        return "grok"
    if "ollama" in key:
        return "ollama"
    return "assemblyai"


def provider_status() -> Dict[str, bool]:
    return {
        "assemblyai_voice": bool(ASSEMBLYAI_API_KEY),
        "grok": bool(GROQ_API_KEY),
        "ollama": bool(OLLAMA_BASE_URL),
    }


def _json_post(url: str, payload: Dict[str, Any], headers: Dict[str, str] | None = None) -> Dict[str, Any]:
    serialized = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=serialized, headers=headers or {}, method="POST")
    with request.urlopen(req, timeout=15) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body) if body else {}


def _build_system_context(session: Dict[str, Any] | None) -> str:
    if not session:
        return (
            "You are RELAY, a smart real-time support agent. Keep context, handle interruptions cleanly, "
            "escalate to a human when the issue needs a person, and preserve the full support story."
        )
    summary = session.get("conversation_summary", "Support issue")
    facts = session.get("important_facts", [])
    fact_text = "; ".join(facts[:5]) if facts else "No prior facts recorded."
    return (
        f"You are RELAY, a support AI. Conversation summary: {summary}. Important facts: {fact_text}. "
        "Preserve context across interruptions and escalate to a human when the user asks for help or the issue is critical."
    )


def generate_provider_reply(provider_name: str, user_message: str, session: Dict[str, Any] | None = None) -> str:
    provider = normalize_provider_name(provider_name)
    safe_message = (user_message or "").strip()
    if not safe_message:
        return "Please describe the issue so I can keep the context and decide whether escalation is needed."

    if provider == "assemblyai":
        if ASSEMBLYAI_API_KEY:
            # Voice capture stays on AssemblyAI, while text reasoning is currently limited to Ollama.
            response = generate_provider_reply("ollama", safe_message, session)
            if "not configured" not in response.lower() and "did not respond" not in response.lower() and "failed" not in response.lower():
                return response
        return (
            "I’m listening to your issue and I’ll keep the context updated. Please tell me the problem clearly so I can help or escalate it correctly."
        )

    if provider == "grok":
        if not GROQ_API_KEY:
            return (
                "Grok/Groq is enabled as a fallback text layer, but no API key is configured. Add GROQ_API_KEY (recommended) or GROK_API_KEY to use live reasoning."
            )
        try:
            payload = {
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": _build_system_context(session)},
                    {"role": "user", "content": safe_message},
                ],
                "temperature": 0.4,
            }
            endpoint = f"{GROQ_BASE_URL.rstrip('/')}/chat/completions"
            result = _json_post(
                endpoint,
                payload,
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            choices = result.get("choices", [])
            if choices:
                message = choices[0].get("message", {}).get("content")
                if message:
                    return str(message).strip()
        except Exception:
            pass
        return (
            "Groq is configured, but the live request failed. The system fell back to safe relay support logic while preserving the session context."
        )

    if not OLLAMA_BASE_URL:
        return "Ollama is not configured. Set OLLAMA_BASE_URL to enable the local model route."
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": f"{_build_system_context(session)}\n\nUser: {safe_message}",
            "stream": False,
            "options": {"temperature": 0.4},
        }
        result = _json_post(f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate", payload)
        response = result.get("response")
        if response:
            return str(response).strip()
    except Exception:
        pass
    return (
        "Ollama is available locally, but the model endpoint did not respond. The RELAY support flow still kept the issue context and human handoff ready."
    )


def resolve_text_reply(user_message: str, session: Dict[str, Any] | None = None) -> tuple[str, str]:
    text = (user_message or "").strip()
    if not text:
        return "assemblyai", "Please tell me the problem and I’ll help preserve the context."

    # For now, Groq/Grok is intentionally disabled. Text reply flow is Ollama-only.
    response = generate_provider_reply("ollama", text, session)
    if "not configured" not in response.lower() and "did not respond" not in response.lower() and "failed" not in response.lower():
        return "ollama", response
    return "assemblyai", generate_provider_reply("assemblyai", text, session)


def summarize_support_context(user_message: str, ai_reply: str, session: Dict[str, Any] | None = None) -> str:
    text = (user_message or "").strip()
    if not text:
        return ""

    prompt = (
        "Summarize this support issue in 1-2 clear sentences using only the facts from the customer message. "
        f"Customer message: {text}. AI response: {ai_reply[:200]}."
    )

    if GROQ_API_KEY:
        try:
            payload = {
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            }
            result = _json_post(
                f"{GROQ_BASE_URL.rstrip('/')}/chat/completions",
                payload,
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            choices = result.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content")
                if content:
                    return str(content).strip()
        except Exception:
            pass

    if OLLAMA_BASE_URL:
        try:
            payload = {
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3},
            }
            result = _json_post(f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate", payload)
            response = result.get("response")
            if response:
                return str(response).strip()
        except Exception:
            pass

    return f"Customer reported: {text[:220]}."
