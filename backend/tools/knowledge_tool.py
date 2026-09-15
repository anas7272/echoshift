from __future__ import annotations

from typing import Dict, List

from backend.rag.retriever import simple_search


def search_knowledge(query: str) -> Dict[str, List[str]]:
    return {"results": simple_search(query, limit=5)}
