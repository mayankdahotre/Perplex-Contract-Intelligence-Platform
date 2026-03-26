"""
Risk Scoring Service
Analyzes contracts for legal risks and generates structured risk assessments.
"""

import os
import json
from openai import OpenAI


RISK_CATEGORIES = {
    "termination_risk": "Termination & Exit",
    "financial_risk": "Financial Exposure",
    "ip_risk": "IP & Ownership Risk",
    "liability_risk": "Liability & Indemnification",
    "compliance_risk": "Compliance & Regulatory",
    "confidentiality_risk": "Confidentiality Breach Risk",
    "dispute_risk": "Dispute Resolution Risk",
    "operational_risk": "Operational & Performance Risk",
}

SYSTEM_PROMPT = """You are a senior contract risk analyst.
Evaluate the provided contract text for legal and business risks.
Respond ONLY with valid JSON — no markdown, no explanation outside JSON."""

RISK_PROMPT = """Analyze this contract for legal and business risks.

Provide a comprehensive risk assessment with:
1. An overall risk score (0-100, where 100 = highest risk)
2. Category scores for each risk area (0-100)
3. Top risk flags (specific problematic clauses or missing provisions)
4. Missing provisions (important clauses that should be present but aren't)
5. Executive summary (3-4 sentences plain English)
6. Recommendations (actionable items, max 5)

Risk categories to score:
- termination_risk
- financial_risk
- ip_risk
- liability_risk
- compliance_risk
- confidentiality_risk
- dispute_risk
- operational_risk

Respond ONLY with this JSON:
{{
  "overall_score": 0-100,
  "risk_level": "low|medium|high|critical",
  "category_scores": {{
    "termination_risk": 0,
    "financial_risk": 0,
    "ip_risk": 0,
    "liability_risk": 0,
    "compliance_risk": 0,
    "confidentiality_risk": 0,
    "dispute_risk": 0,
    "operational_risk": 0
  }},
  "risk_flags": [
    {{
      "severity": "high|medium|low",
      "category": "...",
      "title": "...",
      "description": "...",
      "clause_excerpt": "..."
    }}
  ],
  "missing_provisions": ["..."],
  "executive_summary": "...",
  "recommendations": ["..."]
}}

CONTRACT TEXT:
{text}"""


class RiskScoringService:
    """
    Generates structured risk scores and flags for contracts.
    """

    def __init__(self):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4o")
        self.high_threshold = int(os.environ.get("RISK_SCORE_HIGH_THRESHOLD", "70"))
        self.medium_threshold = int(os.environ.get("RISK_SCORE_MEDIUM_THRESHOLD", "40"))

    def score(self, full_text: str, chunks: list[dict]) -> dict:
        """
        Generate a complete risk assessment.
        Samples strategically from beginning, middle, and end of contract.
        """
        context = self._build_risk_context(chunks, full_text)
        raw = self._llm_score(context)
        return self._normalize(raw)

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _build_risk_context(self, chunks: list[dict], full_text: str, max_chars: int = 14000) -> str:
        """
        Build context for risk scoring — sample from start, middle, end
        to ensure coverage of the full contract.
        """
        if len(full_text) <= max_chars:
            return full_text

        third = max_chars // 3
        start = full_text[:third]
        mid_start = len(full_text) // 2 - third // 2
        middle = full_text[mid_start : mid_start + third]
        end = full_text[-third:]
        return f"{start}\n\n[...middle section...]\n\n{middle}\n\n[...end section...]\n\n{end}"

    def _llm_score(self, context: str) -> dict:
        """Call LLM for risk scoring."""
        prompt = RISK_PROMPT.format(text=context)
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
            return json.loads(content)
        except Exception as e:
            print(f"[RiskScoring] LLM error: {e}")
            return self._empty_assessment()

    def _normalize(self, raw: dict) -> dict:
        """Normalize and enrich raw LLM output."""
        score = int(raw.get("overall_score", 50))
        score = max(0, min(100, score))

        # Determine risk level
        if score >= self.high_threshold:
            risk_level = "high" if score < 85 else "critical"
        elif score >= self.medium_threshold:
            risk_level = "medium"
        else:
            risk_level = "low"

        # Normalize category scores
        category_scores = {}
        for key, label in RISK_CATEGORIES.items():
            raw_score = raw.get("category_scores", {}).get(key, 0)
            category_scores[key] = {
                "label": label,
                "score": max(0, min(100, int(raw_score))),
            }

        # Sort risk flags by severity
        severity_order = {"high": 0, "medium": 1, "low": 2}
        flags = sorted(
            raw.get("risk_flags", []),
            key=lambda f: severity_order.get(f.get("severity", "low"), 3),
        )

        return {
            "overall_score": score,
            "risk_level": risk_level,
            "category_scores": category_scores,
            "risk_flags": flags,
            "missing_provisions": raw.get("missing_provisions", []),
            "executive_summary": raw.get("executive_summary", ""),
            "recommendations": raw.get("recommendations", []),
            "risk_categories_meta": RISK_CATEGORIES,
        }

    def _empty_assessment(self) -> dict:
        return {
            "overall_score": 0,
            "risk_level": "unknown",
            "category_scores": {k: 0 for k in RISK_CATEGORIES},
            "risk_flags": [],
            "missing_provisions": [],
            "executive_summary": "Risk assessment unavailable.",
            "recommendations": [],
        }
