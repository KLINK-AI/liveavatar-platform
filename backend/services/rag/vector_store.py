"""
Vector Store wrapper for Qdrant.

Handles embedding storage and semantic search with per-tenant isolation
via separate Qdrant collections.
"""

from typing import Optional
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


class VectorStore:
    """Qdrant-based vector store with embedding generation."""

    def __init__(self):
        self.client = AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
        )
        self.embedding_client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        self.embedding_model = settings.embedding_model
        self.vector_size = 1536  # text-embedding-3-small

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

    async def embed_text(self, text: str) -> list[float]:
        """Generate an embedding vector for a text string."""
        response = await self.embedding_client.embeddings.create(
            model=self.embedding_model,
            input=text,
        )
        return response.data[0].embedding

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
        query_vector = await self.embed_text(query)

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

        results = await self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=top_k,
            score_threshold=score_threshold,
            query_filter=search_filter,
        )

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
