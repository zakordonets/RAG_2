from __future__ import annotations

import time
from typing import Iterable
from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, SparseVector
from app.config import CONFIG
from app.services.embeddings import embed_dense_batch, embed_sparse_batch
import uuid
from ingestion.chunker import text_hash


client = QdrantClient(url=CONFIG.qdrant_url, api_key=CONFIG.qdrant_api_key or None)


def upsert_chunks(chunks: list[dict]) -> int:
    points: list[PointStruct] = []
    texts = [c["text"] for c in chunks]
    dense_vecs = embed_dense_batch(texts)
    sparse_vecs = embed_sparse_batch(texts)

    for i, ch in enumerate(chunks):
        # deterministic id → UUID из sha256-хэша
        raw_hash = ch.get("id") or text_hash(ch["text"])  # 64-символьный hex
        hex32 = raw_hash.replace("-", "")[:32]
        pid = str(uuid.UUID(hex=hex32))
        payload = ch.get("payload", {})
        payload.update({"hash": pid})
        point_kwargs = {
            "id": pid,
            "vector": {"dense": dense_vecs[i]},
            "payload": payload,
        }
        # Добавляем sparse только если сервис включён и вернул непустые индексы
        try:
            sv = sparse_vecs[i]
            if isinstance(sv, dict) and ("indices" in sv and "values" in sv) and sv.get("indices"):
                point_kwargs["sparse_vectors"] = {"sparse": SparseVector(indices=sv["indices"], values=[float(v) for v in sv["values"]])}
        except Exception:
            pass
        points.append(PointStruct(**point_kwargs))

    if not points:
        return 0
    client.upsert(collection_name=CONFIG.qdrant_collection, points=points)
    return len(points)


