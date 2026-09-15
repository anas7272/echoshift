import json
import os
import time
from urllib import request

import streamlit as st
from dotenv import load_dotenv

load_dotenv()
for env_file in (".env", "env/.env"):
    if os.path.exists(env_file):
        load_dotenv(env_file)

from backend.providers import resolve_text_reply, summarize_support_context
from backend.tools.knowledge_tool import search_knowledge

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8005")

st.set_page_config(
    page_title="RELAY Control Center",
    page_icon="🎙️",
    layout="wide",
)

st.markdown(
    """
    <style>
        .stApp { background: linear-gradient(180deg, #07111d 0%, #0d1727 100%); }
        div[data-testid="stSidebar"] {
            background: rgba(15, 23, 42, 0.96);
            border-right: 1px solid rgba(148, 163, 184, 0.15);
        }
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;

        }
        h1 {
            font-size: 2.6rem !important;
            letter-spacing: -0.05em;
            margin-bottom: 0.2rem;
        }
        h2, h3, h4 {
            letter-spacing: -0.02em;
        }
        .stChatMessage {
            border-radius: 16px;
            padding: 0.5rem 0.75rem;
        }
        .stSelectbox, .stRadio, .stButton > button, .stTextInput input {
            border-radius: 12px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


st.title("RELAY — Human-aware support AI")
st.caption("AI acts. Humans take over when it matters.")

st.warning("Real microphone capture is only reliable on the local browser voice page. Streamlit runs in a sandboxed iframe, and browsers block mic access there.")
st.link_button("Open live voice page", "http://localhost:8005")

st.info("Use the local browser page for green live mic, blue audio meter, and real AssemblyAI voice input. Streamlit remains for chat and session flow.")


def api_get(path: str):
    try:
        with request.urlopen(f"{BACKEND_URL}{path}", timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # pragma: no cover - runtime safety
        return {"error": str(exc)}


def api_post(path: str, params=None, payload=None):
    url = f"{BACKEND_URL}{path}"
    if params:
        query = "&".join(f"{key}={value}" for key, value in params.items())
        url = f"{url}?{query}"
    try:
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = request.Request(url, data=data, headers=headers, method="POST")
        with request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # pragma: no cover - runtime safety
        return {"error": str(exc)}


def extract_customer_name(message: str):
    text = (message or "").strip()
    if not text:
        return ""

    lower = text.lower()
    if "my name is" in lower:
        remainder = text.split("my name is", 1)[1].strip()
        if remainder:
            return remainder.split()[0]
    if "i am " in lower:
        remainder = text.split("i am", 1)[1].strip()
        if remainder:
            return remainder.split()[0]
    if "call me " in lower:
        remainder = text.split("call me", 1)[1].strip()
        if remainder:
            return remainder.split()[0]
    return ""


def looks_like_complaint(message: str) -> bool:
    text = (message or "").lower()
    complaint_words = [
        "issue", "problem", "complaint", "not working", "failed", "error", "bug",
        "cannot", "can't", "unable", "help", "login", "account", "payment",
        "refund", "delay", "slow", "broken", "stuck", "wrong", "missing"
    ]
    return any(word in text for word in complaint_words)


def update_session_from_user(message: str, ai_reply: str):
    msg = (message or "").strip()
    if not msg:
        return

    customer_name = extract_customer_name(msg)
    facts = []
    if any(word in msg.lower() for word in ["locked", "login", "password", "cannot access", "account"]):
        facts.append("Customer reports an account access or login problem.")
    if any(word in msg.lower() for word in ["interrupt", "wait", "actually", "not exactly", "wrong"]):
        facts.append("Customer corrected the earlier issue while continuing the conversation.")
    if any(word in msg.lower() for word in ["human", "agent", "talk to a person", "escalate"]):
        facts.append("Customer explicitly asked for a human agent.")
    if not facts:
        facts.append(f"Customer said: {msg[:160]}")

    summary = summarize_support_context(msg, ai_reply)
    recent_conversation = [
        *((api_get("/api/session") or {}).get("session", {}).get("recent_conversation", [])),
        {"role": "user", "text": msg},
        {"role": "ai", "text": ai_reply},
    ]

    payload = {
        "customer_name": customer_name,
        "recent_user_message": msg,
        "recent_ai_message": ai_reply,
        "recent_conversation": recent_conversation[-8:],
        "important_facts": facts,
        "conversation_summary": summary,
        "current_issue": "" if "account" not in msg.lower() else "account_access_issue",
        "current_intent": "support_help_request",
        "status": "LISTENING",
        "human_status": "AWAITING_HUMAN",
    }
    api_post("/api/session/update", payload=payload)


def get_session_state():
    payload = api_get("/api/session")
    if not payload or "error" in payload:
        return {
            "session_id": "demo-session-001",
            "customer_name": "",
            "current_issue": "",
            "current_intent": "support_help_request",
            "language": "hinglish",
            "status": "LISTENING",
            "human_status": "AWAITING_HUMAN",
            "escalation_requested": False,
            "important_facts": [],
            "recent_conversation": [],
            "handoff": None,
        }
    session = payload.get("session", {})
    return session


def generate_reply(user_message: str, session: dict, provider: str = "AssemblyAI Voice"):
    text = user_message.strip()
    if not text:
        return "Please tell me the issue and I’ll keep the context with the conversation."

    extracted_name = extract_customer_name(text)
    current_name = (session or {}).get("customer_name") or ""
    name = current_name or extracted_name

    lower = text.lower()
    if not name and "my name is" in lower:
        return "Thanks. I’ve got your name — now tell me what happened, and I’ll keep the context updated."

    if not name and looks_like_complaint(text):
        return "Sure — to keep things clean, may I get your name and a quick summary of the issue?"

    lower = text.lower()
    if any(word in lower for word in ["human", "agent", "support", "escalate", "talk to a person", "speak to a human"]):
        escalation = api_post("/api/session/escalate", params={"reason": "user_requested_human_support"})
        handoff = escalation.get("handoff") or {}
        if handoff:
            return (
                "I’ve escalated the conversation and prepared a human handoff. "
                f"Reason: {handoff.get('escalation_reason', 'user_requested_human_support')}. "
                "A human agent will receive the preserved context."
            )
        return "I’ve flagged this for human support and preserved the context for takeover."

    if any(word in lower for word in ["interrupt", "wait", "actually", "not exactly", "wrong", "misunderstood"]):
        api_post("/api/session/interruption")
        return (
            "Thanks for clarifying. I’ve updated the context and I’m continuing from the corrected issue. "
            "I’ll keep the latest information in the handoff summary."
        )

    selected_provider, provider_response = resolve_text_reply(text, session)
    if selected_provider == "assemblyai":
        knowledge = search_knowledge(text)
        results = " ".join(knowledge.get("results", []))
        return f"{provider_response} Relevant guidance: {results[:220]}"
    return provider_response


st.title("RELAY — Human-aware support AI")
st.caption("AI acts. Humans take over when it matters.")

with st.sidebar:
    st.subheader("Live session")
    session = get_session_state()
    st.metric("Customer", session.get("customer_name", "Customer"))
    st.metric("Issue", session.get("current_issue", "support_issue_pending"))
    st.metric("Status", session.get("status", "LISTENING"))
    st.metric("Human", session.get("human_status", "AWAITING_HUMAN"))

    st.caption("Current text model: Ollama only. Groq is disabled for now while the API is failing.")
    if st.button("Trigger interruption", use_container_width=True):
        api_post("/api/session/interruption")
        st.success("Interruption recorded and context updated.")
        time.sleep(0.5)
        st.rerun()

    if st.button("Escalate to human", use_container_width=True):
        escalation = api_post("/api/session/escalate", params={"reason": "user_requested_human_support"})
        if escalation.get("handoff"):
            st.success("Human handoff prepared.")
        else:
            st.warning("Escalation call failed.")
        st.rerun()

    st.markdown("---")
    st.caption("Voice uses AssemblyAI; text uses Ollama only for now.")

chat_tab, handoff_tab = st.tabs(["Chat", "Human handoff"])

with chat_tab:
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "Hey, I’m RELAY. Tell me what’s going on and I’ll keep the context in sync."}
        ]

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    with st.form(key="support_form"):
        input_col, send_col, mic_col = st.columns([5, 1.2, 1.2])
        user_prompt = input_col.text_input("Type your support message...", key="support_input")

        submitted = send_col.form_submit_button("Send", use_container_width=True)
        microphone = mic_col.form_submit_button("🎙️", help="Voice capture is ready for AssemblyAI in live mode", use_container_width=True)

        if submitted and user_prompt.strip():
            st.session_state.messages.append({"role": "user", "content": user_prompt})
            with st.chat_message("user"):
                st.markdown(user_prompt)
            reply = generate_reply(user_prompt, session)
            update_session_from_user(user_prompt, reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})
            with st.chat_message("assistant"):
                st.markdown(reply)
            st.rerun()

        if microphone:
            st.info("Voice mode is ready for AssemblyAI. Use the live voice flow for spoken input.")

with handoff_tab:
    handoff = (api_get("/api/session/handoff") or {}).get("handoff")
    if handoff:
        st.subheader("Handoff summary")
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"Customer: {handoff.get('customer_name', session.get('customer_name', 'Customer'))}")
            st.write(f"Session: {handoff.get('session_id', session.get('session_id', 'demo-session-001'))}")
            st.write(f"Language: {handoff.get('language', session.get('language', 'hinglish'))}")
            st.write(f"Intent: {handoff.get('intent', session.get('current_intent', 'support_help_request'))}")
        with col2:
            st.write(f"Issue: {handoff.get('issue', session.get('current_issue', 'support_issue_pending'))}")
            st.write(f"Escalation: {handoff.get('escalation_reason', 'user_requested_human_support')}")
            st.write(f"Status: {handoff.get('status', session.get('status', 'READY_FOR_TAKEOVER'))}")
        st.write("Summary")
        st.write(handoff.get("summary", "Context preserved and ready for handoff."))
        st.write("Important facts")
        for fact in handoff.get("important_facts", []):
            st.write("-", fact)
    else:
        st.info("No handoff packet yet. Escalate the conversation to prepare one.")

bottom = st.container()
with bottom:
    st.markdown("---")
    st.caption("Live context is generated from the newest user input, not a stale demo record.")
