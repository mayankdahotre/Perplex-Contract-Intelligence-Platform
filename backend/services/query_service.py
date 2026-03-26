"""
RAG Query Service
Retrieval-Augmented Generation for answering questions over contracts.
"""

import os
from openai import OpenAI
from backend.services.embedding_service import VectorStore


SYSTEM_PROMPT = """You are a legal contract analysis assistant with expertise in contract law.
Answer questions about the provided contract using ONLY the retrieved context.
Be precise, cite specific clauses when possible, and flag ambiguities.
If the answer is not in the context, say so clearly — do not hallucinate."""

QA_PROMPT = """You are reviewing a legal contract. Using the retrieved contract excerpts below,
answer the user's question accurately and concisely.

If the excerpts do not contain enough information, say:
"The contract does not appear to address this directly" and explain what related information is available.

Retrieved Contract Excerpts:
{context}

Question: {question}

Answer (be precise, reference specific clauses where possible):"""

SUMMARY_PROMPT = """You are a legal analyst. Provide a comprehensive executive summary of this contract.

Include:
1. **Parties**: Who are the contracting parties?
2. **Purpose**: What is the contract for?
3. **Key Terms**: Main obligations, deliverables, and timelines
4. **Financial Terms**: Payment amounts, schedules, and conditions
5. **Duration**: Contract term and renewal conditions
6. **Key Risks**: 2-3 most significant risk areas (brief)

Be concise but thorough. Use plain English where possible.

Contract Text (excerpt):
{text}"""


class QueryService:
    """
    Handles RAG-based Q&A and summary generation for contracts.
    """

    def __init__(self, index_dir: str):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4o")
        self.vector_store = VectorStore(index_dir)

    def answer(self, doc_id: str, question: str, chat_history: list[dict] = None) -> dict:
        """
        Answer a question about a specific contract using RAG.
        Returns answer text with source chunks.
        """
        # Retrieve relevant chunks
        retrieved = self.vector_store.retrieve(doc_id, question)
        if not retrieved:
            return {
                "answer": "I could not find relevant information in the contract to answer this question.",
                "sources": [],
                "question": question,
            }

        # Build context from retrieved chunks
        context_parts = []
        for i, chunk in enumerate(retrieved, 1):
            page = chunk.get("page_num", "?")
            context_parts.append(f"[Excerpt {i}, Page {page}]\n{chunk['text']}")
        context = "\n\n".join(context_parts)

        # Build messages with optional chat history
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if chat_history:
            for msg in chat_history[-6:]:  # last 3 turns
                messages.append(msg)

        messages.append({
            "role": "user",
            "content": QA_PROMPT.format(context=context, question=question),
        })

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,
            max_tokens=1500,
        )
        answer = response.choices[0].message.content.strip()

        # Format sources
        sources = [
            {
                "chunk_id": c.get("chunk_id"),
                "page_num": c.get("page_num"),
                "section": c.get("section"),
                "score": round(c.get("score", 0), 3),
                "text_preview": c["text"][:200] + "..." if len(c["text"]) > 200 else c["text"],
            }
            for c in retrieved
        ]

        return {
            "answer": answer,
            "sources": sources,
            "question": question,
            "chunks_retrieved": len(retrieved),
        }

    def summarize(self, full_text: str) -> dict:
        """Generate an executive summary of the contract."""
        # Use first 12k chars for summary context
        excerpt = full_text[:12000]
        if len(full_text) > 12000:
            excerpt += f"\n\n[... {len(full_text) - 12000} additional characters not shown ...]"

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a senior legal analyst specializing in contract review."},
                {"role": "user", "content": SUMMARY_PROMPT.format(text=excerpt)},
            ],
            temperature=0.2,
            max_tokens=1500,
        )
        summary = response.choices[0].message.content.strip()
        return {"summary": summary}
