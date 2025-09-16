from __future__ import annotations

from flask import Blueprint, request, jsonify
from loguru import logger
from app.services.orchestrator import handle_query
from app.validation import validate_query_data

bp = Blueprint("chat", __name__)


@bp.post("/query")
def chat_query():
    """
    Обработка запросов чата с валидацией и санитизацией.

    Request body:
        {
            "message": "Текст запроса",
            "channel": "telegram|web|api",
            "chat_id": "ID чата"
        }

    Returns:
        JSON ответ с результатом обработки
    """
    try:
        # Получение и валидация данных
        payload = request.get_json(silent=True) or {}
        validated_data, errors = validate_query_data(payload)

        if errors:
            logger.warning(f"Validation errors: {errors}")
            return jsonify({
                "error": "validation_failed",
                "message": "Некорректные данные запроса",
                "details": errors
            }), 400

        # Обработка запроса
        result = handle_query(
            channel=validated_data["channel"],
            chat_id=validated_data["chat_id"],
            message=validated_data["message"]
        )

        # Добавляем метаданные запроса
        result["request_id"] = request.headers.get("X-Request-ID", "unknown")

        return jsonify(result)

    except Exception as e:
        logger.error(f"Unexpected error in chat_query: {e}", exc_info=True)
        return jsonify({
            "error": "internal_error",
            "message": "Внутренняя ошибка сервера. Попробуйте позже."
        }), 500
