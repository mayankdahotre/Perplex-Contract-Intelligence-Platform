"""
Clause Extraction & Classification Service
Identifies and classifies key legal provisions from contract text.
"""

import os
import re
import json
from typing import Optional
from openai import OpenAI


# ── Clause taxonomy ────────────────────────────────────────────────────────────
CLAUSE_TYPES = {
    "termination": {
        "label": "Termination",
        "description": "Conditions and procedures for ending the contract",
        "icon": "⚡",
        "color": "#ef4444",
        "keywords": [
            "terminat", "cancel", "expir", "end of term", "cessation",
            "notice of termination", "termination for cause", "termination for convenience"
        ],
    },
    "payment": {
        "label": "Payment",
        "description": "Payment terms, amounts, schedules, and penalties",
        "icon": "💰",
        "color": "#f59e0b",
        "keywords": [
            "payment", "invoice", "fee", "compensation", "remuneration",
            "price", "cost", "charge", "billing", "due date", "overdue", "penalty"
        ],
    },
    "confidentiality": {
        "label": "Confidentiality",
        "description": "Non-disclosure and data protection obligations",
        "icon": "🔒",
        "color": "#6366f1",
        "keywords": [
            "confidential", "non-disclosure", "NDA", "proprietary", "trade secret",
            "disclose", "privacy", "sensitive information"
        ],
    },
    "indemnification": {
        "label": "Indemnification",
        "description": "Liability and indemnity obligations between parties",
        "icon": "🛡️",
        "color": "#8b5cf6",
        "keywords": [
            "indemnif", "hold harmless", "defend", "liability", "damages",
            "indemnitor", "indemnified party"
        ],
    },
    "limitation_of_liability": {
        "label": "Limitation of Liability",
        "description": "Caps on damages and exclusions of liability",
        "icon": "⚖️",
        "color": "#ec4899",
        "keywords": [
            "limitation of liability", "limit.*liability", "cap on damages",
            "in no event", "not liable", "exclude.*liability", "consequential damages"
        ],
    },
    "intellectual_property": {
        "label": "Intellectual Property",
        "description": "IP ownership, licensing, and usage rights",
        "icon": "💡",
        "color": "#06b6d4",
        "keywords": [
            "intellectual property", "copyright", "patent", "trademark",
            "license", "ownership", "work for hire", "assignment of rights"
        ],
    },
    "dispute_resolution": {
        "label": "Dispute Resolution",
        "description": "Processes for resolving disputes (arbitration, litigation, mediation)",
        "icon": "🏛️",
        "color": "#10b981",
        "keywords": [
            "dispute", "arbitration", "mediation", "litigation", "governing law",
            "jurisdiction", "venue", "court"
        ],
    },
    "force_majeure": {
        "label": "Force Majeure",
        "description": "Excused performance due to extraordinary events",
        "icon": "🌪️",
        "color": "#f97316",
        "keywords": [
            "force majeure", "act of god", "beyond.*control", "unforeseeable",
            "pandemic", "natural disaster", "war", "earthquake"
        ],
    },
    "renewal": {
        "label": "Renewal & Duration",
        "description": "Contract term, renewal conditions, and auto-renewal clauses",
        "icon": "🔄",
        "color": "#14b8a6",
        "keywords": [
            "renew", "auto-renew", "term of", "initial term", "anniversary",
            "extension", "duration", "effective date"
        ],
    },
    "warranties": {
        "label": "Warranties & Representations",
        "description": "Guarantees, warranties, and representations made by parties",
        "icon": "✅",
        "color": "#84cc16",
        "keywords": [
            "warrant", "represent", "guarantee", "as-is", "disclaimer",
            "fitness for purpose", "merchantability"
        ],
    },
}

SYSTEM_PROMPT = """You are a senior legal analyst specializing in contract review.
Your task is to extract key clauses from contract text and classify them.
Always respond with valid JSON only — no preamble, no markdown code fences."""

EXTRACTION_PROMPT = """Analyze the following contract text and extract key legal clauses.

For each clause found, provide:
- clause_type: one of {clause_types}
- title: a concise title (max 10 words)
- text: the exact or near-exact clause text (max 400 chars)
- page_ref: page number if identifiable, else null
- risk_indicators: list of concerning phrases or terms (max 3)
- notes: 1-2 sentence plain-English explanation

Respond ONLY with this JSON structure:
{{
  "clauses": [
    {{
      "clause_type": "...",
      "title": "...",
      "text": "...",
      "page_ref": null,
      "risk_indicators": ["..."],
      "notes": "..."
    }}
  ]
}}

CONTRACT TEXT:
{text}"""


class ClauseExtractionService:
    """
    Extracts and classifies legal clauses from contract text.
    Uses a hybrid approach: keyword pre-filtering + LLM classification.
    """

    def __init__(self):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4o")

    # ── Public API ─────────────────────────────────────────────────────────────

    def extract_clauses(self, full_text: str, chunks: list[dict]) -> list[dict]:
        """
        Extract clauses from the contract.
        Sends relevant chunks to the LLM for extraction + classification.
        Returns list of clause dicts.
        """
        # Keyword pre-filter to find high-signal chunks
        relevant_chunks = self._filter_relevant_chunks(chunks)

        # Build focused context for the LLM (limit tokens)
        context = self._build_context(relevant_chunks, max_chars=12000)

        raw_clauses = self._llm_extract(context)
        clauses = self._enrich_clauses(raw_clauses, full_text)
        return clauses

    def get_clause_types(self) -> dict:
        return CLAUSE_TYPES

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _filter_relevant_chunks(self, chunks: list[dict]) -> list[dict]:
        """Score chunks by keyword density and return top candidates."""
        scored = []
        all_keywords = [kw for ct in CLAUSE_TYPES.values() for kw in ct["keywords"]]
        pattern = re.compile(
            "|".join(re.escape(kw) for kw in all_keywords), re.IGNORECASE
        )
        for chunk in chunks:
            hits = len(pattern.findall(chunk["text"]))
            if hits > 0:
                scored.append((hits, chunk))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:20]]  # top 20 chunks

    def _build_context(self, chunks: list[dict], max_chars: int = 12000) -> str:
        """Build a context string from chunks with page markers."""
        parts = []
        total = 0
        for chunk in chunks:
            header = f"\n--- Page {chunk.get('page_num', '?')} ---\n"
            block = header + chunk["text"]
            if total + len(block) > max_chars:
                break
            parts.append(block)
            total += len(block)
        return "\n".join(parts)

    def _llm_extract(self, context: str) -> list[dict]:
        """Call LLM to extract and classify clauses."""
        clause_type_keys = ", ".join(CLAUSE_TYPES.keys())
        prompt = EXTRACTION_PROMPT.format(
            clause_types=clause_type_keys, text=context
        )
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=3000,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            data = json.loads(content)
            return data.get("clauses", [])
        except Exception as e:
            print(f"[ClauseExtraction] LLM error: {e}")
            return []

    def _enrich_clauses(self, raw_clauses: list[dict], full_text: str) -> list[dict]:
        """Enrich clauses with display metadata from CLAUSE_TYPES."""
        enriched = []
        for clause in raw_clauses:
            ct_key = clause.get("clause_type", "")
            ct_meta = CLAUSE_TYPES.get(ct_key, {})
            enriched.append({
                **clause,
                "label": ct_meta.get("label", ct_key.replace("_", " ").title()),
                "icon": ct_meta.get("icon", "📄"),
                "color": ct_meta.get("color", "#6b7280"),
                "description": ct_meta.get("description", ""),
            })
        return enriched
