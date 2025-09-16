from __future__ import annotations

from flask import Blueprint, request, jsonify
from loguru import logger
from app.services.orchestrator import handle_query
from app.validation import validate_query_data
from app.security import validate_request, security_monitor

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

        # Дополнительная проверка безопасности
        user_id = validated_data.get("chat_id", "unknown")
        security_result = validate_request(
            user_id=user_id,
            message=validated_data["message"],
            channel=validated_data["channel"],
            chat_id=validated_data["chat_id"]
        )

        if not security_result["is_valid"]:
            logger.warning(f"Security validation failed for user {user_id}: {security_result['errors']}")
            return jsonify({
                "error": "security_validation_failed",
                "message": "Запрос не прошел проверку безопасности",
                "details": security_result["errors"]
            }), 400

        # Используем санитизированное сообщение
        sanitized_message = security_result["sanitized_message"]

        # Обработка запроса
        result = handle_query(
            channel=validated_data["channel"],
            chat_id=validated_data["chat_id"],
            message=sanitized_message
        )

        # Добавляем метаданные запроса
        result["request_id"] = request.headers.get("X-Request-ID", "unknown")
        result["security_warnings"] = security_result.get("warnings", [])

        return jsonify(result)

    except Exception as e:
        logger.error(f"Unexpected error in chat_query: {e}", exc_info=True)
        return jsonify({
            "error": "internal_error",
            "message": "Внутренняя ошибка сервера. Попробуйте позже."
        }), 500
