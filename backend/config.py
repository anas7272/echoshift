from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY") or os.getenv("ASSEMBLYAI_KEY")
ASSEMBLYAI_WS_URL = "wss://agents.assemblyai.com/v1/ws"
SESSION_DEFAULT_LANGUAGE = "hinglish"


def env_path(*parts: str) -> Path:
    return BASE_DIR.joinpath(*parts)
