"""
Contract Routes
Handles PDF upload, analysis pipeline orchestration, and contract CRUD.
"""

import os
import threading
from datetime import datetime
from pathlib import Path
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename

from backend.services.ingestion_service import PDFIngestionService
from backend.services.embedding_service import VectorStore
from backend.services.clause_service import ClauseExtractionService
from backend.services.risk_service import RiskScoringService
from backend.services.query_service import QueryService
from backend.services.contract_store import ContractStore

contract_bp = Blueprint("contracts", __name__)

ALLOWED_EXTENSIONS = {"pdf"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_store() -> ContractStore:
    return ContractStore(Path(current_app.config["UPLOAD_FOLDER"]).parent)


def get_vector_store() -> VectorStore:
    return VectorStore(current_app.config["INDEX_FOLDER"])


# ── Upload & Analyze ───────────────────────────────────────────────────────────

@contract_bp.route("/upload", methods=["POST"])
def upload_contract():
    """Upload a PDF contract and start the analysis pipeline."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400
    if not allowed_file(file.filename):
        return jsonify({"error": "Only PDF files are accepted"}), 400

    # Save file
    filename = secure_filename(file.filename)
    upload_dir = current_app.config["UPLOAD_FOLDER"]
    save_path = os.path.join(upload_dir, filename)
    file.save(save_path)

    # Ingest (extract text + chunk) synchronously to get doc_id
    ingestion = PDFIngestionService(
        chunk_size=int(os.environ.get("CHUNK_SIZE", 1000)),
        chunk_overlap=int(os.environ.get("CHUNK_OVERLAP", 200)),
    )
    try:
        doc_data = ingestion.ingest(save_path)
    except Exception as e:
        return jsonify({"error": f"PDF parsing failed: {str(e)}"}), 422

    doc_id = doc_data["doc_id"]
    store = get_store()
    index_dir = current_app.config["INDEX_FOLDER"]

    # Persist initial record
    store.save(doc_id, {
        "doc_id": doc_id,
        "filename": filename,
        "file_path": save_path,
        "metadata": doc_data["metadata"],
        "page_count": doc_data["page_count"],
        "chunk_count": doc_data["chunk_count"],
        "status": "indexing",
        "created_at": datetime.utcnow().isoformat(),
    })

    # Run heavy analysis in background thread
    thread = threading.Thread(
        target=_run_analysis_pipeline,
        args=(doc_id, doc_data, save_path, index_dir, current_app._get_current_object()),
        daemon=True,
    )
    thread.start()

    return jsonify({
        "doc_id": doc_id,
        "filename": filename,
        "page_count": doc_data["page_count"],
        "chunk_count": doc_data["chunk_count"],
        "status": "indexing",
        "message": "Contract uploaded. Analysis running in background.",
    }), 202


def _run_analysis_pipeline(doc_id: str, doc_data: dict, save_path: str, index_dir: str, app):
    """Background analysis: embed → extract clauses → risk score → summarize."""
    with app.app_context():
        store = ContractStore(Path(save_path).parent.parent)
        vector_store = VectorStore(index_dir)

        try:
            # 1. Index embeddings
            store.update_status(doc_id, "indexing")
            vector_store.index_document(doc_id, doc_data["chunks"])

            # 2. Extract clauses
            store.update_status(doc_id, "extracting_clauses")
            clause_svc = ClauseExtractionService()
            clauses = clause_svc.extract_clauses(doc_data["full_text"], doc_data["chunks"])
            store.update_analysis(doc_id, "clauses", clauses)

            # 3. Risk scoring
            store.update_status(doc_id, "scoring_risk")
            risk_svc = RiskScoringService()
            risk = risk_svc.score(doc_data["full_text"], doc_data["chunks"])
            store.update_analysis(doc_id, "risk", risk)

            # 4. Summary
            store.update_status(doc_id, "summarizing")
            query_svc = QueryService(index_dir)
            summary_result = query_svc.summarize(doc_data["full_text"])
            store.update_analysis(doc_id, "summary", summary_result["summary"])

            # Done
            store.update_status(doc_id, "ready")

        except Exception as e:
            print(f"[Pipeline] Error for {doc_id}: {e}")
            store.update_status(doc_id, "error", str(e))


# ── List & Get ─────────────────────────────────────────────────────────────────

@contract_bp.route("/", methods=["GET"])
def list_contracts():
    """List all uploaded contracts."""
    store = get_store()
    contracts = store.list_all()
    # Strip full_text from list response
    clean = []
    for c in contracts:
        c.pop("full_text", None)
        clean.append(c)
    return jsonify({"contracts": clean})


@contract_bp.route("/<doc_id>", methods=["GET"])
def get_contract(doc_id: str):
    """Get a single contract with all analysis results."""
    store = get_store()
    record = store.get(doc_id)
    if not record:
        return jsonify({"error": "Contract not found"}), 404
    record.pop("full_text", None)
    return jsonify(record)


@contract_bp.route("/<doc_id>/status", methods=["GET"])
def get_status(doc_id: str):
    """Poll analysis status."""
    store = get_store()
    record = store.get(doc_id)
    if not record:
        return jsonify({"error": "Contract not found"}), 404
    return jsonify({
        "doc_id": doc_id,
        "status": record.get("status", "unknown"),
        "error": record.get("error"),
    })


@contract_bp.route("/<doc_id>", methods=["DELETE"])
def delete_contract(doc_id: str):
    """Delete a contract and its index."""
    store = get_store()
    record = store.get(doc_id)
    if not record:
        return jsonify({"error": "Contract not found"}), 404

    # Delete files
    try:
        file_path = record.get("file_path")
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
    except Exception:
        pass

    # Delete index files
    index_dir = current_app.config["INDEX_FOLDER"]
    for ext in [".faiss", ".meta.json"]:
        p = Path(index_dir) / f"{doc_id}{ext}"
        if p.exists():
            p.unlink()

    store.delete(doc_id)
    return jsonify({"message": "Contract deleted"})
