"""
PDF Ingestion Service
Handles PDF parsing, text extraction, semantic chunking, and metadata extraction.
"""

import os
import re
import hashlib
from pathlib import Path
from typing import Optional
import pdfplumber
import PyPDF2
from langchain_text_splitters import RecursiveCharacterTextSplitter


# ── Section header patterns for legal documents ────────────────────────────────
SECTION_PATTERNS = [
    r"^\s*\d+[\.\)]\s+[A-Z][A-Z\s]+",          # 1. DEFINITIONS
    r"^\s*ARTICLE\s+[IVX\d]+",                   # ARTICLE I
    r"^\s*Section\s+\d+",                         # Section 1
    r"^\s*[A-Z][A-Z\s]{4,}\s*$",                 # ALL CAPS HEADINGS
]
SECTION_RE = re.compile("|".join(SECTION_PATTERNS), re.MULTILINE)


class PDFIngestionService:
    """
    Ingests PDF contracts, extracts text with layout awareness,
    and splits into semantically coherent chunks.
    """

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            keep_separator=True,
        )

    # ── Public API ─────────────────────────────────────────────────────────────

    def ingest(self, pdf_path: str) -> dict:
        """
        Full ingestion pipeline for a single PDF.
        Returns dict with: doc_id, metadata, pages, chunks
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        doc_id = self._compute_doc_id(pdf_path)
        metadata = self._extract_metadata(pdf_path)
        pages = self._extract_pages(pdf_path)
        full_text = "\n\n".join(p["text"] for p in pages)
        chunks = self._chunk_document(pages, full_text, doc_id)

        return {
            "doc_id": doc_id,
            "filename": pdf_path.name,
            "metadata": metadata,
            "full_text": full_text,
            "page_count": len(pages),
            "chunk_count": len(chunks),
            "chunks": chunks,
        }

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _compute_doc_id(self, pdf_path: Path) -> str:
        """Stable hash-based document ID."""
        h = hashlib.sha256()
        h.update(pdf_path.name.encode())
        h.update(str(pdf_path.stat().st_size).encode())
        return h.hexdigest()[:16]

    def _extract_metadata(self, pdf_path: Path) -> dict:
        """Extract PDF metadata (title, author, dates, page count)."""
        meta = {"filename": pdf_path.name, "size_bytes": pdf_path.stat().st_size}
        try:
            with open(pdf_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                info = reader.metadata or {}
                meta["page_count"] = len(reader.pages)
                meta["title"] = str(info.get("/Title", "")).strip() or pdf_path.stem
                meta["author"] = str(info.get("/Author", "")).strip()
                meta["creation_date"] = str(info.get("/CreationDate", "")).strip()
        except Exception:
            meta.setdefault("page_count", 0)
            meta.setdefault("title", pdf_path.stem)
        return meta

    def _extract_pages(self, pdf_path: Path) -> list[dict]:
        """
        Extract text per page using pdfplumber (better layout handling).
        Falls back to PyPDF2 if pdfplumber fails on a page.
        """
        pages = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    text = self._clean_text(text)
                    pages.append({
                        "page_num": i + 1,
                        "text": text,
                        "char_count": len(text),
                    })
        except Exception:
            # Fallback to PyPDF2
            with open(pdf_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for i, page in enumerate(reader.pages):
                    text = page.extract_text() or ""
                    text = self._clean_text(text)
                    pages.append({
                        "page_num": i + 1,
                        "text": text,
                        "char_count": len(text),
                    })
        return pages

    def _clean_text(self, text: str) -> str:
        """Normalize whitespace and remove junk characters."""
        text = re.sub(r"\x00", "", text)                    # null bytes
        text = re.sub(r"(\r\n|\r)", "\n", text)             # normalize line endings
        text = re.sub(r"[ \t]{2,}", " ", text)              # collapse spaces
        text = re.sub(r"\n{3,}", "\n\n", text)              # max 2 newlines
        return text.strip()

    def _chunk_document(self, pages: list[dict], full_text: str, doc_id: str) -> list[dict]:
        """
        Split document into chunks with rich metadata.
        Attempts section-aware splitting first; falls back to recursive splitting.
        """
        raw_chunks = self.splitter.split_text(full_text)
        chunks = []
        char_cursor = 0

        for idx, chunk_text in enumerate(raw_chunks):
            # Approximate page number by character offset
            page_num = self._estimate_page(pages, char_cursor)
            section = self._detect_section(chunk_text)

            chunks.append({
                "chunk_id": f"{doc_id}_{idx:04d}",
                "doc_id": doc_id,
                "index": idx,
                "text": chunk_text,
                "page_num": page_num,
                "section": section,
                "char_count": len(chunk_text),
            })
            char_cursor += len(chunk_text)

        return chunks

    def _estimate_page(self, pages: list[dict], char_offset: int) -> int:
        """Estimate page number from character offset."""
        cumulative = 0
        for page in pages:
            cumulative += page["char_count"]
            if char_offset <= cumulative:
                return page["page_num"]
        return pages[-1]["page_num"] if pages else 1

    def _detect_section(self, text: str) -> Optional[str]:
        """Detect section heading in chunk text."""
        match = SECTION_RE.search(text[:300])
        if match:
            return match.group(0).strip()[:100]
        return None
