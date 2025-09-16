from __future__ import annotations
import time
from loguru import logger

from typing import Any
from app.services.query_processing import process_query
from app.services.embeddings import embed_dense, embed_sparse
from app.services.retrieval import hybrid_search
from app.services.rerank import rerank
from app.services.llm_router import generate_answer
from app.metrics import metrics_collector


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
    
    # Инициализация метрик
    error_type = None
    status = "success"
    
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
            embedding_start = time.time()
            q_dense = embed_dense(normalized)
            embedding_duration = time.time() - embedding_start
            logger.info(f"Dense embedding in {embedding_duration:.2f}s")
            metrics_collector.record_embedding_duration("dense", embedding_duration)
        except Exception as e:
            logger.error(f"Dense embedding failed: {e}")
            error_type = "embedding_failed"
            metrics_collector.record_error("embedding_failed", "dense_embedding")
            return {
                "error": "embedding_failed",
                "message": "Сервис эмбеддингов временно недоступен. Попробуйте позже.",
                "sources": [],
                "channel": channel,
                "chat_id": chat_id
            }

        # 3. Sparse Embedding
        try:
            sparse_start = time.time()
            q_sparse = embed_sparse(normalized)
            sparse_duration = time.time() - sparse_start
            logger.info(f"Sparse embedding in {sparse_duration:.2f}s")
            metrics_collector.record_embedding_duration("sparse", sparse_duration)
        except Exception as e:
            logger.warning(f"Sparse embedding failed: {e}, continuing with dense only")
            q_sparse = {"indices": [], "values": []}
            metrics_collector.record_error("sparse_embedding_failed", "sparse_embedding")

        # 4. Hybrid Search
        try:
            search_start = time.time()
            candidates = hybrid_search(q_dense, q_sparse, k=20, boosts=boosts)
            search_duration = time.time() - search_start
            logger.info(f"Hybrid search in {search_duration:.2f}s")
            metrics_collector.record_search_duration("hybrid", search_duration)
            
            if not candidates:
                logger.warning("No candidates found in search")
                error_type = "no_results"
                metrics_collector.record_error("no_results", "search")
                return {
                    "error": "no_results",
                    "message": "К сожалению, не удалось найти релевантную информацию по вашему запросу. Попробуйте переформулировать вопрос или использовать другие ключевые слова.",
                    "sources": [],
                    "channel": channel,
                    "chat_id": chat_id
                }
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            error_type = "search_failed"
            metrics_collector.record_error("search_failed", "hybrid_search")
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
            llm_start = time.time()
            answer = generate_answer(normalized, top_docs, policy={})
            llm_duration = time.time() - llm_start
            logger.info(f"LLM generation in {llm_duration:.2f}s")
            metrics_collector.record_llm_duration("default", llm_duration)
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            error_type = "llm_failed"
            metrics_collector.record_error("llm_failed", "llm_generation")
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
        
        # Записываем метрики успешного запроса
        metrics_collector.record_query(channel, status, error_type)
        metrics_collector.record_query_duration("total", total_time)
        metrics_collector.record_search_results("hybrid", len(candidates))
        
        return {
            "answer": answer,
            "sources": sources,
            "channel": channel,
            "chat_id": chat_id,
            "processing_time": total_time
        }

    except Exception as e:
        logger.error(f"Unexpected error in handle_query: {e}", exc_info=True)
        
        # Записываем метрики ошибки
        error_type = type(e).__name__
        status = "error"
        metrics_collector.record_query(channel, status, error_type)
        metrics_collector.record_error(error_type, "orchestrator")
        
        return {
            "error": "internal_error",
            "message": "Произошла внутренняя ошибка. Попробуйте позже или обратитесь в поддержку.",
            "sources": [],
            "channel": channel,
            "chat_id": chat_id
        }
