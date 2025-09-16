from __future__ import annotations

from typing import Any
import os
import threading
from FlagEmbedding import FlagReranker
from app.config import CONFIG


_reranker = None
_lock = threading.Lock()


def _get_reranker() -> FlagReranker:
    global _reranker
    if _reranker is None:
        with _lock:
            if _reranker is None:
                os.environ["OMP_NUM_THREADS"] = str(CONFIG.reranker_threads)
                os.environ["MKL_NUM_THREADS"] = str(CONFIG.reranker_threads)
                _reranker = FlagReranker(CONFIG.reranker_model, use_fp16=False, device=CONFIG.reranker_device)
    return _reranker


def rerank(query: str, candidates: list[dict], top_n: int = 10) -> list[dict]:
    """Реализация bge-reranker-v2-m3 на CPU.
    Возвращает top_n документов, отсортированных по релевантности к запросу.
    """
    if not candidates:
        return []
    reranker = _get_reranker()
    pairs = [[query, (c.get("payload", {}) or {}).get("text") or (c.get("payload", {}) or {}).get("title") or ""] for c in candidates]
    scores = reranker.compute_score(pairs, normalize=True)
    for i, s in enumerate(scores):
        candidates[i]["rerank_score"] = float(s)
    candidates.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
    return candidates[:top_n]


