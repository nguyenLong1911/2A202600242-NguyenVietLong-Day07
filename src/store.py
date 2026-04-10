from __future__ import annotations

from typing import Any, Callable

from .chunking import _dot
from .embeddings import _mock_embed
from .models import Document


class EmbeddingStore:
    """
    A vector store for text chunks.

    Tries to use ChromaDB if available; falls back to an in-memory store.
    The embedding_fn parameter allows injection of mock embeddings for tests.
    """

    def __init__(
        self,
        collection_name: str = "documents",
        embedding_fn: Callable[[str], list[float]] | None = None,
    ) -> None:
        self._embedding_fn = embedding_fn or _mock_embed
        self._collection_name = collection_name
        self._use_chroma = False
        self._store: list[dict[str, Any]] = []
        self._collection = None
        self._next_index = 0

        try:
            import chromadb

            client = chromadb.Client()
            self._collection = client.get_or_create_collection(name=self._collection_name)
            self._use_chroma = True
        except Exception:
            self._use_chroma = False
            self._collection = None

    def _make_record(self, doc: Document, embedding: list[float] | None = None) -> dict[str, Any]:
        metadata = dict(doc.metadata or {})
        metadata.setdefault("doc_id", doc.id)
        record_id = f"{doc.id}_{self._next_index}"
        self._next_index += 1
        return {
            "id": record_id,
            "content": doc.content,
            "metadata": metadata,
            "embedding": embedding if embedding is not None else self._embedding_fn(doc.content),
        }

    def _search_records(self, query: str, records: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
        if top_k <= 0:
            return []

        query_embedding = self._embedding_fn(query)
        scored = []
        for record in records:
            score = _dot(query_embedding, record["embedding"])
            scored.append(
                {
                    "id": record["id"],
                    "content": record["content"],
                    "metadata": record["metadata"],
                    "score": score,
                }
            )

        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:top_k]

    def add_documents(self, docs: list[Document]) -> None:
        """
        Embed each document's content and store it.

        For ChromaDB: use collection.add(ids=[...], documents=[...], embeddings=[...])
        For in-memory: append dicts to self._store
        """
        if not docs:
            return

        embed_many = getattr(self._embedding_fn, "embed_many", None)

        if self._use_chroma and self._collection is not None:
            ids: list[str] = []
            documents: list[str] = []
            metadatas: list[dict[str, Any]] = []
            contents = [doc.content for doc in docs]
            embeddings = embed_many(contents) if callable(embed_many) else [self._embedding_fn(content) for content in contents]
            for doc, embedding in zip(docs, embeddings):
                record = self._make_record(doc, embedding=embedding)
                ids.append(record["id"])
                documents.append(record["content"])
                metadatas.append(record["metadata"])
            self._collection.add(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)
            return

        if callable(embed_many):
            embeddings = embed_many([doc.content for doc in docs])
            for doc, embedding in zip(docs, embeddings):
                self._store.append(self._make_record(doc, embedding=embedding))
            return

        for doc in docs:
            self._store.append(self._make_record(doc))

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """
        Find the top_k most similar documents to query.

        For in-memory: compute dot product of query embedding vs all stored embeddings.
        """
        if top_k <= 0:
            return []

        if self._use_chroma and self._collection is not None:
            result = self._collection.query(query_embeddings=[self._embedding_fn(query)], n_results=top_k)
            ids = result.get("ids", [[]])[0]
            documents = result.get("documents", [[]])[0]
            metadatas = result.get("metadatas", [[]])[0]
            distances = result.get("distances", [[]])[0]

            items: list[dict[str, Any]] = []
            for index, item_id in enumerate(ids):
                distance = distances[index] if index < len(distances) else 0.0
                items.append(
                    {
                        "id": item_id,
                        "content": documents[index] if index < len(documents) else "",
                        "metadata": metadatas[index] if index < len(metadatas) else {},
                        "score": -float(distance),
                    }
                )
            items.sort(key=lambda item: item["score"], reverse=True)
            return items

        return self._search_records(query=query, records=self._store, top_k=top_k)

    def get_collection_size(self) -> int:
        """Return the total number of stored chunks."""
        if self._use_chroma and self._collection is not None:
            return int(self._collection.count())
        return len(self._store)

    def search_with_filter(self, query: str, top_k: int = 3, metadata_filter: dict = None) -> list[dict]:
        """
        Search with optional metadata pre-filtering.

        First filter stored chunks by metadata_filter, then run similarity search.
        """
        if top_k <= 0:
            return []

        metadata_filter = metadata_filter or {}

        if self._use_chroma and self._collection is not None:
            if metadata_filter:
                result = self._collection.query(
                    query_embeddings=[self._embedding_fn(query)],
                    n_results=top_k,
                    where=metadata_filter,
                )
                ids = result.get("ids", [[]])[0]
                documents = result.get("documents", [[]])[0]
                metadatas = result.get("metadatas", [[]])[0]
                distances = result.get("distances", [[]])[0]
                items: list[dict[str, Any]] = []
                for index, item_id in enumerate(ids):
                    distance = distances[index] if index < len(distances) else 0.0
                    items.append(
                        {
                            "id": item_id,
                            "content": documents[index] if index < len(documents) else "",
                            "metadata": metadatas[index] if index < len(metadatas) else {},
                            "score": -float(distance),
                        }
                    )
                items.sort(key=lambda item: item["score"], reverse=True)
                return items

            return self.search(query=query, top_k=top_k)

        if not metadata_filter:
            candidates = self._store
        else:
            candidates = []
            for record in self._store:
                metadata = record.get("metadata") or {}
                if all(metadata.get(key) == value for key, value in metadata_filter.items()):
                    candidates.append(record)

        return self._search_records(query=query, records=candidates, top_k=top_k)

    def delete_document(self, doc_id: str) -> bool:
        """
        Remove all chunks belonging to a document.

        Returns True if any chunks were removed, False otherwise.
        """
        if self._use_chroma and self._collection is not None:
            matched = self._collection.get(where={"doc_id": doc_id})
            ids = matched.get("ids", []) if matched else []
            if not ids:
                return False
            self._collection.delete(ids=ids)
            return True

        size_before = len(self._store)
        self._store = [record for record in self._store if (record.get("metadata") or {}).get("doc_id") != doc_id]
        return len(self._store) < size_before
