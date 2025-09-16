from __future__ import annotations
import time
from loguru import logger

from typing import Any
from app.services.query_processing import process_query
from app.services.embeddings import embed_dense, embed_sparse
from app.services.retrieval import hybrid_search
from app.services.rerank import rerank
from app.services.llm_router import generate_answer


class RAGError(Exception):
    """Базовый класс для ошибок RAG системы."""
    pass


class EmbeddingError(RAGError):
    """Ошибка при создании эмбеддингов."""
    pass


class SearchError(RAGError):
    """Ошибка при поиске в векторной базе."""
    pass


class LLMError(RAGError):
    """Ошибка при обращении к LLM."""
    pass


def handle_query(channel: str, chat_id: str, message: str) -> dict[str, Any]:
    """
    Обрабатывает пользовательский запрос с comprehensive error handling.
    
    Args:
        channel: Канал связи (telegram, web, etc.)
        chat_id: ID чата
        message: Текст сообщения
        
    Returns:
        Словарь с ответом, источниками и метаданными
        
    Raises:
        RAGError: При критических ошибках системы
    """
    start = time.time()
    logger.info(f"Processing query: {message[:100]}...")
    
    try:
        # 1. Query Processing
        try:
            qp = process_query(message)
            normalized = qp["normalized_text"]
            boosts = qp.get("boosts", {})
            logger.info(f"Query processed in {time.time() - start:.2f}s")
        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            return {
                "error": "query_processing_failed",
                "message": "Ошибка обработки запроса. Попробуйте переформулировать вопрос.",
                "sources": [],
                "channel": channel,
                "chat_id": chat_id
            }

        # 2. Dense Embedding
        try:
            q_dense = embed_dense(normalized)
            logger.info(f"Dense embedding in {time.time() - start:.2f}s")
        except Exception as e:
            logger.error(f"Dense embedding failed: {e}")
            return {
                "error": "embedding_failed",
                "message": "Сервис эмбеддингов временно недоступен. Попробуйте позже.",
                "sources": [],
                "channel": channel,
                "chat_id": chat_id
            }

        # 3. Sparse Embedding
        try:
            q_sparse = embed_sparse(normalized)
            logger.info(f"Sparse embedding in {time.time() - start:.2f}s")
        except Exception as e:
            logger.warning(f"Sparse embedding failed: {e}, continuing with dense only")
            q_sparse = {"indices": [], "values": []}

        # 4. Hybrid Search
        try:
            candidates = hybrid_search(q_dense, q_sparse, k=20, boosts=boosts)
            logger.info(f"Hybrid search in {time.time() - start:.2f}s")
            
            if not candidates:
                logger.warning("No candidates found in search")
                return {
                    "error": "no_results",
                    "message": "К сожалению, не удалось найти релевантную информацию по вашему запросу. Попробуйте переформулировать вопрос или использовать другие ключевые слова.",
                    "sources": [],
                    "channel": channel,
                    "chat_id": chat_id
                }
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            return {
                "error": "search_failed",
                "message": "Ошибка поиска в базе знаний. Попробуйте позже.",
                "sources": [],
                "channel": channel,
                "chat_id": chat_id
            }

        # 5. Reranking
        try:
            top_docs = rerank(normalized, candidates, top_n=10)
            logger.info(f"Rerank in {time.time() - start:.2f}s")
        except Exception as e:
            logger.warning(f"Reranking failed: {e}, using original candidates")
            top_docs = candidates[:10]

        # 6. LLM Generation
        try:
            answer = generate_answer(normalized, top_docs, policy={})
            logger.info(f"LLM generation in {time.time() - start:.2f}s")
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return {
                "error": "llm_failed",
                "message": "Сервис генерации ответов временно недоступен. Попробуйте позже.",
                "sources": [],
                "channel": channel,
                "chat_id": chat_id
            }

        # 7. Extract sources
        sources = []
        try:
            for d in top_docs:
                pl = d.get("payload", {}) or {}
                if pl.get("url"):
                    sources.append({
                        "title": pl.get("title", "Документация"),
                        "url": pl.get("url")
                    })
        except Exception as e:
            logger.warning(f"Source extraction failed: {e}")

        total_time = time.time() - start
        logger.info(f"Total processing time: {total_time:.2f}s")
        
        return {
            "answer": answer,
            "sources": sources,
            "channel": channel,
            "chat_id": chat_id,
            "processing_time": total_time
        }

    except Exception as e:
        logger.error(f"Unexpected error in handle_query: {e}", exc_info=True)
        return {
            "error": "internal_error",
            "message": "Произошла внутренняя ошибка. Попробуйте позже или обратитесь в поддержку.",
            "sources": [],
            "channel": channel,
            "chat_id": chat_id
        }


