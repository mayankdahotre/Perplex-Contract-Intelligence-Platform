from flask import Blueprint, jsonify
import os

health_bp = Blueprint("health", __name__)

@health_bp.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "Perplex Contract Intelligence Platform",
        "llm_provider": os.environ.get("LLM_PROVIDER", "openai"),
        "model": os.environ.get("OPENAI_MODEL", "gpt-4o"),
    })
