from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class SessionState:
    session_id: str = "demo-session-001"
    customer_name: str = ""
    language: str = "hinglish"
    current_intent: str = "support_help_request"
    current_issue: str = ""
    conversation_summary: str = ""
    important_facts: List[str] = field(default_factory=list)
    recent_user_message: str = ""
    recent_ai_message: str = ""
    actions_taken: List[str] = field(default_factory=lambda: ["acknowledge_issue", "request_details", "track_context"])
    interruption_count: int = 0
    escalation_requested: bool = False
    escalation_reason: str | None = None
    status: str = "LISTENING"
    human_status: str = "AWAITING_HUMAN"
    recent_conversation: List[Dict[str, str]] = field(default_factory=list)
    handoff: Dict[str, Any] | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "customer_name": self.customer_name,
            "language": self.language,
            "current_intent": self.current_intent,
            "current_issue": self.current_issue,
            "conversation_summary": self.conversation_summary,
            "important_facts": self.important_facts,
            "recent_user_message": self.recent_user_message,
            "recent_ai_message": self.recent_ai_message,
            "actions_taken": self.actions_taken,
            "interruption_count": self.interruption_count,
            "escalation_requested": self.escalation_requested,
            "escalation_reason": self.escalation_reason,
            "status": self.status,
            "human_status": self.human_status,
            "recent_conversation": self.recent_conversation,
            "handoff": self.handoff,
        }
