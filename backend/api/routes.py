from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query

from backend.agent.state import SessionState
from backend.escalation.engine import EscalationEngine

router = APIRouter(prefix="/api")
state = SessionState()
trace: List[Dict[str, Any]] = [{
    "type": "agent_state",
    "state": "LISTENING",
    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "metadata": {"message": "Session initialized."},
}]
engine = EscalationEngine()


def log_event(event_type: str, **payload: Any) -> None:
    trace.append({
        "type": event_type,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        **payload,
    })


@router.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok", "service": "RELAY"}


@router.get("/session")
async def get_session() -> Dict[str, Any]:
    return {"session": state.to_dict(), "trace": trace}


@router.post("/session/interruption")
async def interruption() -> Dict[str, Any]:
    state.interruption_count += 1
    state.status = "INTERRUPTED"
    state.actions_taken.append("context_updated_after_interruption")
    state.important_facts.append("User interrupted while AI was speaking and clarified the issue.")
    state.conversation_summary = "Customer clarified the issue after interrupting the AI response; context was preserved and updated."
    state.recent_user_message = "Wait, that’s not exactly what happened."
    log_event("interruption", message="User interrupted the AI response.", interruption_count=state.interruption_count)
    log_event("agent_state", state="CONTEXT_UPDATED", metadata={"message": "Conversation context updated."})
    return {"status": "ok", "session": state.to_dict()}


@router.post("/session/escalate")
async def escalate(reason: str = Query(default="user_requested_human_support")) -> Dict[str, Any]:
    status = engine.evaluate(state, reason)
    state.escalation_requested = status["escalate"]
    state.escalation_reason = reason if status["escalate"] else None
    state.status = "ESCALATING" if status["escalate"] else state.status
    state.human_status = "READY_FOR_TAKEOVER" if status["escalate"] else "AWAITING_HUMAN"
    state.handoff = status.get("handoff")
    log_event("escalation", reason=reason, message="Escalation requested.")
    return {"status": "ok", "handoff": state.handoff, "session": state.to_dict()}


@router.post("/session/takeover")
async def takeover() -> Dict[str, Any]:
    state.status = "HUMAN_ACTIVE"
    state.human_status = "HUMAN_JOINED"
    log_event("agent_state", state="HUMAN_JOINED", metadata={"message": "Human agent joined."})
    return {"status": "ok", "session": state.to_dict()}


@router.get("/session/handoff")
async def handoff() -> Dict[str, Any]:
    if state.handoff is None:
        state.handoff = engine.build_handoff(state)
    return {"handoff": state.handoff}


@router.get("/session/trace")
async def session_trace() -> Dict[str, Any]:
    return {"trace": trace}
