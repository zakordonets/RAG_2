from __future__ import annotations

from flask import Blueprint, jsonify, request
from ingestion.pipeline import crawl_and_index

bp = Blueprint("admin", __name__)


@bp.post("/reindex")
def reindex():
    force_full = bool((request.get_json(silent=True) or {}).get("force_full", False))
    res = crawl_and_index(incremental=not force_full)
    return jsonify({"status": "done", "force_full": force_full, **res})


@bp.get("/health")
def health():
    return jsonify({"status": "ok"})


