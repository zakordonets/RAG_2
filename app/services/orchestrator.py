from __future__ import annotations
import time
from loguru import logger

from typing import Any
from app.services.query_processing import process_query
from app.services.embeddings import embed_dense, embed_sparse
from app.services.retrieval import hybrid_search
from app.services.rerank import rerank
from app.services.llm_router import generate_answer


def handle_query(channel: str, chat_id: str, message: str) -> dict[str, Any]:
    start = time.time()
    logger.info(f"Processing query: {message[:100]}...")
    
    qp = process_query(message)
    normalized = qp["normalized_text"]
    boosts = qp.get("boosts", {})
    logger.info(f"Query processed in {time.time() - start:.2f}s")

    q_dense = embed_dense(normalized)
    logger.info(f"Dense embedding in {time.time() - start:.2f}s")
    q_sparse = embed_sparse(normalized)  # expects {indices: [...], values: [...]} or compatible
    logger.info(f"Sparse embedding in {time.time() - start:.2f}s")

    candidates = hybrid_search(q_dense, q_sparse, k=20, boosts=boosts)
    logger.info(f"Hybrid search in {time.time() - start:.2f}s")
    top_docs = rerank(normalized, candidates, top_n=10)
    logger.info(f"Rerank in {time.time() - start:.2f}s")
    answer = generate_answer(normalized, top_docs, policy={})
    logger.info(f"LLM generation in {time.time() - start:.2f}s")

    sources = []
    for d in top_docs:
        pl = d.get("payload", {}) or {}
        if pl.get("url"):
            sources.append({"title": pl.get("title"), "url": pl.get("url")})

    logger.info(f"Total processing time: {time.time() - start:.2f}s")
    return {"answer": answer, "sources": sources, "channel": channel, "chat_id": chat_id}


