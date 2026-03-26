"""
Embedding & Vector Store Service
Manages embedding generation and FAISS-based retrieval with threshold calibration.
"""

import os
import json
import pickle
import numpy as np
from pathlib import Path
from typing import Optional
from openai import OpenAI
import faiss


class EmbeddingService:
    """
    Generates embeddings via OpenAI text-embedding-3-small.
    Caches embeddings to avoid redundant API calls.
    """

    def __init__(self):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.model = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        self.dimension = 1536  # text-embedding-3-small output dim

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        """Embed a batch of texts. Returns (N, D) float32 array."""
        if not texts:
            return np.zeros((0, self.dimension), dtype=np.float32)

        # OpenAI allows up to 2048 inputs per batch; chunk if needed
        all_embeddings = []
        batch_size = 100
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = self.client.embeddings.create(model=self.model, input=batch)
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)

        return np.array(all_embeddings, dtype=np.float32)

    def embed_query(self, query: str) -> np.ndarray:
        """Embed a single query. Returns (1, D) float32 array."""
        return self.embed_texts([query])


class VectorStore:
    """
    FAISS-based vector store with metadata persistence.
    Supports per-document indexes stored on disk.
    """

    def __init__(self, index_dir: str):
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.embedding_service = EmbeddingService()
        self.similarity_threshold = float(
            os.environ.get("SIMILARITY_THRESHOLD", "0.35")
        )
        self.top_k = int(os.environ.get("RETRIEVAL_TOP_K", "6"))

    # ── Index management ───────────────────────────────────────────────────────

    def index_document(self, doc_id: str, chunks: list[dict]) -> int:
        """
        Embed chunks and build a FAISS inner-product index for the document.
        Returns number of indexed chunks.
        """
        texts = [c["text"] for c in chunks]
        embeddings = self.embedding_service.embed_texts(texts)

        # Normalize for cosine similarity via inner product
        faiss.normalize_L2(embeddings)

        index = faiss.IndexFlatIP(embeddings.shape[1])
        index.add(embeddings)

        self._save_index(doc_id, index, chunks)
        return len(chunks)

    def retrieve(
        self, doc_id: str, query: str, top_k: Optional[int] = None
    ) -> list[dict]:
        """
        Retrieve top-k relevant chunks for a query from a document's index.
        Applies similarity threshold filtering.
        """
        index, chunks = self._load_index(doc_id)
        if index is None:
            return []

        k = top_k or self.top_k
        query_embedding = self.embedding_service.embed_query(query)
        faiss.normalize_L2(query_embedding)

        scores, indices = index.search(query_embedding, min(k, index.ntotal))
        scores = scores[0]
        indices = indices[0]

        results = []
        for score, idx in zip(scores, indices):
            if idx == -1:
                continue
            if float(score) < self.similarity_threshold:
                continue
            chunk = chunks[idx].copy()
            chunk["score"] = float(score)
            results.append(chunk)

        return results

    def document_exists(self, doc_id: str) -> bool:
        index_path = self.index_dir / f"{doc_id}.faiss"
        meta_path = self.index_dir / f"{doc_id}.meta.json"
        return index_path.exists() and meta_path.exists()

    # ── Persistence helpers ────────────────────────────────────────────────────

    def _save_index(self, doc_id: str, index: faiss.Index, chunks: list[dict]):
        faiss.write_index(index, str(self.index_dir / f"{doc_id}.faiss"))
        with open(self.index_dir / f"{doc_id}.meta.json", "w") as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)

    def _load_index(self, doc_id: str) -> tuple:
        index_path = self.index_dir / f"{doc_id}.faiss"
        meta_path = self.index_dir / f"{doc_id}.meta.json"
        if not index_path.exists():
            return None, []
        index = faiss.read_index(str(index_path))
        with open(meta_path) as f:
            chunks = json.load(f)
        return index, chunks
