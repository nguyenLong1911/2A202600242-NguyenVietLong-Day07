from typing import Callable

from .store import EmbeddingStore


class KnowledgeBaseAgent:
    """
    An agent that answers questions using a vector knowledge base.

    Retrieval-augmented generation (RAG) pattern:
        1. Retrieve top-k relevant chunks from the store.
        2. Build a prompt with the chunks as context.
        3. Call the LLM to generate an answer.
    """

    def __init__(self, store: EmbeddingStore, llm_fn: Callable[[str], str]) -> None:
        self.store = store
        self.llm_fn = llm_fn

    def _is_summary_query(self, query: str) -> bool:
        query_lc = query.lower()
        summary_markers = [
            "summarize",
            "summary",
            "key information",
            "loaded files",
            "tong quan",
            "tom tat",
        ]
        return any(marker in query_lc for marker in summary_markers)

    def _dedupe_by_source(self, items: list[dict], limit: int) -> list[dict]:
        selected: list[dict] = []
        seen_sources: set[str] = set()

        for item in items:
            source = (item.get("metadata") or {}).get("source", "unknown")
            if source in seen_sources:
                continue
            seen_sources.add(source)
            selected.append(item)
            if len(selected) >= limit:
                break

        if len(selected) < limit:
            for item in items:
                if item in selected:
                    continue
                selected.append(item)
                if len(selected) >= limit:
                    break
        return selected

    def answer(self, question: str, top_k: int = 3) -> str:
        query = (question or "").strip()
        if not query:
            return "Please provide a question."

        if self._is_summary_query(query):
            raw_retrieved = self.store.search(query, top_k=max(top_k * 6, 24))
            retrieved = self._dedupe_by_source(raw_retrieved, limit=max(top_k, 6))
        else:
            retrieved = self.store.search(query, top_k=top_k)

        if not retrieved:
            return "I could not find relevant information in the knowledge base."

        context_lines: list[str] = []
        for index, item in enumerate(retrieved, start=1):
            source = (item.get("metadata") or {}).get("source", "unknown")
            content = item.get("content", "")
            context_lines.append(f"[{index}] source={source}\n{content}")

        context = "\n\n".join(context_lines)
        if self._is_summary_query(query):
            prompt = (
                "You are a helpful assistant. Use only the provided context to write a concise cross-document summary. "
                "Cite source names in parentheses for each major bullet. If context is insufficient, state what is missing.\n\n"
                f"Question:\n{query}\n\n"
                f"Context:\n{context}\n\n"
                "Answer:"
            )
        else:
            prompt = (
                "You are a helpful assistant. Use only the provided context to answer. "
                "If the context is insufficient, say so clearly.\n\n"
                f"Question:\n{query}\n\n"
                f"Context:\n{context}\n\n"
                "Answer:"
            )
        return self.llm_fn(prompt)
