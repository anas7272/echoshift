from __future__ import annotations

from typing import Any, Dict


class SupportTools:
    @staticmethod
    def get_session_context() -> Dict[str, Any]:
        return {"context": "current support session summary"}

    @staticmethod
    def save_support_note(note: str) -> Dict[str, str]:
        return {"saved": "ok", "note": note}

    @staticmethod
    def create_support_ticket(summary: str) -> Dict[str, Any]:
        return {"ticket_id": "SUP-1001", "summary": summary}

    @staticmethod
    def mark_for_human_review(reason: str) -> Dict[str, str]:
        return {"status": "human_review", "reason": reason}
