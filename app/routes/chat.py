from __future__ import annotations

from flask import Blueprint, request, jsonify
from app.services.orchestrator import handle_query

bp = Blueprint("chat", __name__)


@bp.post("/query")
def chat_query():
    payload = request.get_json(silent=True) or {}
    channel = payload.get("channel") or "telegram"
    chat_id = payload.get("chat_id") or ""
    message = payload.get("message") or ""

    if not message:
        return jsonify({"error": "message is required"}), 400

    result = handle_query(channel=channel, chat_id=chat_id, message=message)
    return jsonify(result)



