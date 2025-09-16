from __future__ import annotations

from typing import Iterable
import os
import requests
from loguru import logger
from app.config import CONFIG
from app.caching import cache_embedding, cache_manager
from threading import Lock

# На Windows отключаем symlink'и HuggingFace, чтобы избежать прав доступа
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")

_st_model = None
_st_lock: Lock | None = Lock()


OLLAMA_URL = CONFIG.ollama_url
SPARSE_SERVICE_URL = CONFIG.sparse_service_url
EMBEDDING_MODEL_NAME = CONFIG.embedding_model_name


def _get_st_model():
    global _st_model
    # Ждём инициализацию в многопоточном окружении
    if _st_model is None:
        assert _st_lock is not None
        with _st_lock:
            if _st_model is None:
                from sentence_transformers import SentenceTransformer
                # Явно используем huggingface-id для локальной модели BGE-M3
                hf_model = 'BAAI/bge-m3'
                _st_model = SentenceTransformer(hf_model, device='cpu')
    return _st_model


@cache_embedding(ttl=3600)  # Кэшируем на 1 час
def embed_dense(text: str) -> list[float]:
    """Возвращает dense-эмбеддинг через локальный SentenceTransformers (BAAI/bge-m3)."""
    if not CONFIG.cache_enabled:
        # Если кэширование отключено, выполняем напрямую
        model = _get_st_model()
        vec = model.encode(text, normalize_embeddings=True)
        return vec.tolist()
    
    # Кэшированная версия
    model = _get_st_model()
    vec = model.encode(text, normalize_embeddings=True)
    return vec.tolist()


def embed_dense_batch(texts: Iterable[str]) -> list[list[float]]:
    texts_list = list(texts)
    if not texts_list:
        return []
    model = _get_st_model()
    mat = model.encode(texts_list, normalize_embeddings=True)
    return [row.tolist() for row in mat]


@cache_embedding(ttl=3600)  # Кэшируем на 1 час
def embed_sparse(text: str) -> dict:
    """Возвращает sparse-представление текста (BGE-M3 sparse) через локальный сервис.
    Приводит ответ к формату Qdrant: {indices: [...], values: [...]}.
    """
    if not CONFIG.use_sparse:
        return {"indices": [], "values": []}
    
    if not CONFIG.cache_enabled:
        # Если кэширование отключено, выполняем напрямую
        try:
            resp = requests.post(f"{SPARSE_SERVICE_URL}/embed", json={"text": text}, timeout=60)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning(f"Sparse embedding service failed: {e}")
            return {"indices": [], "values": []}
    else:
        # Кэшированная версия
        try:
            resp = requests.post(f"{SPARSE_SERVICE_URL}/embed", json={"text": text}, timeout=60)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning(f"Sparse embedding service failed: {e}")
            return {"indices": [], "values": []}
    
    # Ожидаемый формат для Qdrant SparseVector: {indices: [...], values: [...]}
    # Если сервис вернул словарь term->weight, конвертируем в списки
    if isinstance(data, dict) and ("indices" not in data or "values" not in data):
        indices = list(data.keys())
        values = [float(data[k]) for k in indices]
        return {"indices": indices, "values": values}
    return data


def embed_sparse_batch(texts: Iterable[str]) -> list[dict[str, float]]:
    return [embed_sparse(t) for t in texts]


