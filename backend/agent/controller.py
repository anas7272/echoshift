from __future__ import annotations

from typing import Any, Dict

from backend.agent.state import SessionState


class ConversationController:
    def __init__(self, state: SessionState) -> None:
        self.state = state

    def update_after_interruption(self, user_message: str) -> Dict[str, Any]:
        self.state.interruption_count += 1
        self.state.status = "INTERRUPTED"
        self.state.actions_taken.append("context_updated_after_interruption")
        self.state.important_facts.append("User interrupted to clarify the issue.")
        self.state.recent_user_message = user_message
        self.state.conversation_summary = "User clarified the issue after interruption; the agent must continue from the updated context."
        return self.state.to_dict()

    def escalate(self, reason: str = "user_requested_human_support") -> Dict[str, Any]:
        self.state.escalation_requested = True
        self.state.escalation_reason = reason
        self.state.status = "ESCALATING"
        self.state.human_status = "READY_FOR_TAKEOVER"
        return self.state.to_dict()
