"""
Query Routes
RAG-based question answering over contracts.
"""

from flask import Blueprint, request, jsonify, current_app
from backend.services.query_service import QueryService
from backend.services.contract_store import ContractStore
from pathlib import Path

query_bp = Blueprint("query", __name__)


def get_store():
    return ContractStore(Path(current_app.config["UPLOAD_FOLDER"]).parent)


@query_bp.route("/<doc_id>", methods=["POST"])
def ask(doc_id: str):
    """Ask a question about a contract."""
    store = get_store()
    record = store.get(doc_id)
    if not record:
        return jsonify({"error": "Contract not found"}), 404
    if record.get("status") != "ready":
        return jsonify({"error": "Contract is still being analyzed. Please wait."}), 202

    body = request.get_json(force=True) or {}
    question = body.get("question", "").strip()
    chat_history = body.get("chat_history", [])

    if not question:
        return jsonify({"error": "Question is required"}), 400
    if len(question) > 1000:
        return jsonify({"error": "Question too long (max 1000 chars)"}), 400

    index_dir = current_app.config["INDEX_FOLDER"]
    query_svc = QueryService(index_dir)

    try:
        result = query_svc.answer(doc_id, question, chat_history)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"Query failed: {str(e)}"}), 500


@query_bp.route("/<doc_id>/summarize", methods=["POST"])
def summarize(doc_id: str):
    """Re-generate the contract summary on demand."""
    store = get_store()
    record = store.get(doc_id)
    if not record:
        return jsonify({"error": "Contract not found"}), 404

    # We need the full text — re-ingest lightweight (read stored file)
    from backend.services.ingestion_service import PDFIngestionService
    file_path = record.get("file_path")
    if not file_path:
        return jsonify({"error": "Source file not available"}), 404

    ingestion = PDFIngestionService()
    doc_data = ingestion.ingest(file_path)

    index_dir = current_app.config["INDEX_FOLDER"]
    query_svc = QueryService(index_dir)
    result = query_svc.summarize(doc_data["full_text"])
    return jsonify(result)
