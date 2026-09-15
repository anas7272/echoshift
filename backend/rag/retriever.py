from __future__ import annotations

from pathlib import Path
from typing import List


BASE_DIR = Path(__file__).resolve().parents[1]
DOC_PATH = BASE_DIR / "knowledge" / "support_manual.md"


def load_manual_text() -> str:
    if DOC_PATH.exists():
        return DOC_PATH.read_text(encoding="utf-8")
    return ""


def simple_search(query: str, limit: int = 3) -> List[str]:
    text = load_manual_text().lower()
    query_lower = query.lower()
    lines = [line.strip() for line in load_manual_text().splitlines() if line.strip()]

    matches: List[str] = []
    for line in lines:
        if query_lower in line.lower():
            matches.append(line)
        if len(matches) >= limit:
            break

    if matches:
        return matches

    return [
        "RELAY supports support conversations, interruption handling, and human escalation.",
        "Use the latest context after the user corrects the issue.",
        "Escalate when the customer needs a human agent or the issue is critical.",
    ][:limit]
