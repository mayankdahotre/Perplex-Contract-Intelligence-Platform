"""
Contract Store
Simple JSON-based persistence for contract metadata and analysis results.
"""

import json
import os
from pathlib import Path
from datetime import datetime


class ContractStore:
    """
    Persists contract metadata, analysis results, and status to disk.
    In production, replace with PostgreSQL / Redis.
    """

    def __init__(self, data_dir: str):
        self.db_path = Path(data_dir) / "contracts.json"
        self._ensure_db()

    def _ensure_db(self):
        if not self.db_path.exists():
            self._write({})

    def _read(self) -> dict:
        with open(self.db_path) as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.db_path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ── CRUD ───────────────────────────────────────────────────────────────────

    def save(self, doc_id: str, record: dict):
        db = self._read()
        db[doc_id] = {
            **record,
            "updated_at": datetime.utcnow().isoformat(),
        }
        self._write(db)

    def get(self, doc_id: str) -> dict | None:
        return self._read().get(doc_id)

    def list_all(self) -> list[dict]:
        db = self._read()
        return sorted(db.values(), key=lambda x: x.get("created_at", ""), reverse=True)

    def delete(self, doc_id: str):
        db = self._read()
        db.pop(doc_id, None)
        self._write(db)

    def update_status(self, doc_id: str, status: str, error: str = None):
        db = self._read()
        if doc_id in db:
            db[doc_id]["status"] = status
            if error:
                db[doc_id]["error"] = error
            db[doc_id]["updated_at"] = datetime.utcnow().isoformat()
            self._write(db)

    def update_analysis(self, doc_id: str, field: str, value):
        db = self._read()
        if doc_id in db:
            db[doc_id][field] = value
            db[doc_id]["updated_at"] = datetime.utcnow().isoformat()
            self._write(db)
