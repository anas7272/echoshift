from __future__ import annotations

import os

from backend.config import ASSEMBLYAI_API_KEY, ASSEMBLYAI_WS_URL


def build_voice_token_request_headers() -> dict:
    return {"Authorization": f"Bearer {ASSEMBLYAI_API_KEY}"} if ASSEMBLYAI_API_KEY else {}


def build_ws_url(token: str) -> str:
    return f"{ASSEMBLYAI_WS_URL}?token={token}"
