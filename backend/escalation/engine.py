from __future__ import annotations

from typing import Any, Dict

from backend.agent.state import SessionState


class EscalationEngine:
    @staticmethod
    def should_escalate(state: SessionState, explicit_reason: str | None = None) -> bool:
        if explicit_reason:
            return True
        if state.interruption_count >= 2:
            return True
        if state.escalation_requested:
            return True
        if state.current_issue in {"high_risk", "manual_review", "requires_human"}:
            return True
        return False

    def evaluate(self, state: SessionState, explicit_reason: str | None = None) -> Dict[str, Any]:
        escalate = self.should_escalate(state, explicit_reason)
        handoff = self.build_handoff(state) if escalate else None
        return {
            "escalate": escalate,
            "reason": explicit_reason or "repeated_attempts_failed",
            "handoff": handoff,
        }

    @staticmethod
    def build_handoff(state: SessionState) -> Dict[str, Any]:
        return {
            "session_id": state.session_id,
            "customer_name": state.customer_name,
            "language": state.language,
            "intent": state.current_intent,
            "issue": state.current_issue,
            "summary": state.conversation_summary,
            "important_facts": state.important_facts,
            "recent_conversation": state.recent_conversation,
            "actions_taken": state.actions_taken,
            "escalation_reason": state.escalation_reason or "user_requested_human_support",
            "status": "READY_FOR_TAKEOVER",
            "timestamp": "now",
        }
