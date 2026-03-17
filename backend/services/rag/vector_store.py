"""
Vector Store wrapper for Qdrant.

Handles embedding storage and semantic search with per-tenant isolation
via separate Qdrant collections.
"""

from typing import Optional
from functools import lru_cache
import hashlib
import time
import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)
import openai
import uuid

from config import get_settings

logger = structlog.get_logger()
settings = get_settings()

# ── Embedding Cache ──
# Caches query embeddings to avoid redundant OpenAI API calls.
# Typical query embeddings are ~6KB each; 500 entries ≈ 3MB RAM.
_EMBEDDING_CACHE_MAX = 500

# ── Singleton ──
_vector_store_instance: "VectorStore | None" = None


def get_vector_store() -> "VectorStore":
    """Return the shared VectorStore singleton (reuses OpenAI + Qdrant clients)."""
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = VectorStore()
    return _vector_store_instance


class VectorStore:
    """Qdrant-based vector store with embedding generation and caching."""

    def __init__(self):
        self.client = AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
            timeout=10,  # 10s timeout prevents hanging
        )
        self.embedding_client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        self.embedding_model = settings.embedding_model
        self.vector_size = 1536  # text-embedding-3-small
        # In-memory embedding cache: hash(text) → (embedding, timestamp)
        self._embed_cache: dict[str, tuple[list[float], float]] = {}

    async def ensure_collection(self, collection_name: str):
        """Create a Qdrant collection if it doesn't exist."""
        collections = await self.client.get_collections()
        existing = [c.name for c in collections.collections]

        if collection_name not in existing:
            await self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE,
                ),
            )
            logger.info("Created Qdrant collection", collection=collection_name)

    def _cache_key(self, text: str) -> str:
        """Generate a cache key for embedding lookup."""
        return hashlib.md5(f"{self.embedding_model}:{text}".encode()).hexdigest()

    def _evict_cache(self):
        """Evict oldest entries if cache exceeds max size."""
        if len(self._embed_cache) > _EMBEDDING_CACHE_MAX:
            # Remove oldest 20% by timestamp
            sorted_keys = sorted(self._embed_cache, key=lambda k: self._embed_cache[k][1])
            for k in sorted_keys[:len(sorted_keys) // 5]:
                del self._embed_cache[k]

    async def embed_text(self, text: str) -> list[float]:
        """Generate an embedding vector — with in-memory cache for queries."""
        cache_key = self._cache_key(text)
        cached = self._embed_cache.get(cache_key)
        if cached:
            logger.debug("Embedding cache HIT", text_len=len(text))
            return cached[0]

        t0 = time.monotonic()
        response = await self.embedding_client.embeddings.create(
            model=self.embedding_model,
            input=text,
        )
        embedding = response.data[0].embedding
        elapsed_ms = round((time.monotonic() - t0) * 1000)

        # Cache the result
        self._embed_cache[cache_key] = (embedding, time.time())
        self._evict_cache()

        logger.info("Embedding generated", model=self.embedding_model,
                     text_len=len(text), elapsed_ms=elapsed_ms,
                     cache_size=len(self._embed_cache))
        return embedding

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts in one call."""
        response = await self.embedding_client.embeddings.create(
            model=self.embedding_model,
            input=texts,
        )
        return [item.embedding for item in response.data]

    async def add_documents(
        self,
        collection_name: str,
        chunks: list[dict],
    ) -> int:
        """
        Add document chunks to the vector store.

        Args:
            collection_name: Qdrant collection (tenant-specific)
            chunks: List of dicts with 'text', 'metadata' keys

        Returns:
            Number of chunks added
        """
        await self.ensure_collection(collection_name)

        texts = [chunk["text"] for chunk in chunks]
        embeddings = await self.embed_texts(texts)

        points = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            points.append(PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "text": chunk["text"],
                    "source": chunk.get("metadata", {}).get("source", "unknown"),
                    "document_id": chunk.get("metadata", {}).get("document_id", ""),
                    "chunk_index": i,
                    **chunk.get("metadata", {}),
                },
            ))

        await self.client.upsert(
            collection_name=collection_name,
            points=points,
        )

        logger.info("Added documents to vector store",
                     collection=collection_name, count=len(points))
        return len(points)

    async def warmup(self):
        """Pre-warm the OpenAI embedding HTTP connection to avoid cold-start latency."""
        try:
            t0 = time.monotonic()
            await self.embedding_client.embeddings.create(
                model=self.embedding_model,
                input="warmup",
            )
            elapsed_ms = round((time.monotonic() - t0) * 1000)
            logger.info("Embedding client warmed up", elapsed_ms=elapsed_ms,
                        model=self.embedding_model)
        except Exception as e:
            logger.warning("Embedding warmup failed (non-critical)", error=str(e))

    async def search(
        self,
        collection_name: str,
        query: str,
        top_k: int = 5,
        score_threshold: float = 0.3,
        document_id: Optional[str] = None,
    ) -> list[dict]:
        """
        Semantic search for relevant document chunks.

        Args:
            collection_name: Qdrant collection to search
            query: User's question/search query
            top_k: Number of results to return
            score_threshold: Minimum similarity score
            document_id: Optional filter by specific document

        Returns:
            List of matching chunks with text, score, and metadata
        """
        t_embed_start = time.monotonic()
        query_vector = await self.embed_text(query)
        t_embed_end = time.monotonic()

        search_filter = None
        if document_id:
            search_filter = Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id),
                    )
                ]
            )

        t_qdrant_start = time.monotonic()
        results = await self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=top_k,
            score_threshold=score_threshold,
            query_filter=search_filter,
        )
        t_qdrant_end = time.monotonic()

        embed_ms = round((t_embed_end - t_embed_start) * 1000)
        qdrant_ms = round((t_qdrant_end - t_qdrant_start) * 1000)
        logger.info("Vector search complete",
                     collection=collection_name,
                     embed_ms=embed_ms, qdrant_ms=qdrant_ms,
                     results=len(results))

        return [
            {
                "text": hit.payload.get("text", ""),
                "score": hit.score,
                "source": hit.payload.get("source", "unknown"),
                "document_id": hit.payload.get("document_id", ""),
                "metadata": {k: v for k, v in hit.payload.items()
                            if k not in ("text",)},
            }
            for hit in results
        ]

    async def delete_document(self, collection_name: str, document_id: str):
        """Delete all chunks belonging to a specific document."""
        await self.client.delete(
            collection_name=collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id),
                    )
                ]
            ),
        )
        logger.info("Deleted document from vector store",
                     collection=collection_name, document_id=document_id)

    async def delete_collection(self, collection_name: str):
        """Delete an entire collection (e.g., when removing a tenant)."""
        await self.client.delete_collection(collection_name=collection_name)
        logger.info("Deleted collection", collection=collection_name)

    async def close(self):
        await self.client.close()
        await self.embedding_client.close()
