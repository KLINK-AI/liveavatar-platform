"""
RAG Pipeline — Orchestrates retrieval-augmented generation.

This is the main entry point for RAG operations:
1. Document ingestion (upload, crawl, API)
2. Semantic search (query → relevant chunks)
3. Context assembly (chunks → formatted context for LLM)
"""

from typing import Optional
import structlog

from services.rag.vector_store import VectorStore, get_vector_store
from services.rag.document_ingester import DocumentIngester
from services.rag.web_crawler import WebCrawler
from services.rag.api_connector import APIConnector

logger = structlog.get_logger()


class RAGPipeline:
    """
    Main RAG orchestration class.
    Each tenant has their own Qdrant collection for data isolation.
    """

    def __init__(self):
        self.vector_store = get_vector_store()
        self.ingester = DocumentIngester()
        self.crawler = WebCrawler()
        self.api_connector = APIConnector()

    # ---- Ingestion Methods ----

    async def ingest_document(
        self,
        collection_name: str,
        file_path: str,
        doc_type: str,
        document_id: str,
        source_name: str,
    ) -> int:
        """
        Ingest a document file into the RAG pipeline.

        Args:
            collection_name: Tenant's Qdrant collection
            file_path: Path to the uploaded file
            doc_type: "pdf", "docx", "txt", "csv"
            document_id: Unique document ID
            source_name: Display name for the source

        Returns:
            Number of chunks indexed
        """
        chunks = await self.ingester.process_document(
            file_path=file_path,
            doc_type=doc_type,
            document_id=document_id,
            source_name=source_name,
        )

        if chunks:
            count = await self.vector_store.add_documents(collection_name, chunks)
            return count

        return 0

    async def ingest_url(
        self,
        collection_name: str,
        url: str,
        document_id: str,
        crawl_site: bool = False,
        max_pages: int = 20,
    ) -> int:
        """
        Ingest content from a URL or crawl an entire site.

        Args:
            collection_name: Tenant's Qdrant collection
            url: URL to crawl
            document_id: Unique document ID
            crawl_site: If True, follow links and crawl multiple pages
            max_pages: Maximum pages to crawl

        Returns:
            Number of chunks indexed
        """
        if crawl_site:
            pages = await self.crawler.crawl_site(url, max_pages=max_pages)
        else:
            page = await self.crawler.crawl_url(url)
            pages = [page] if page["text"].strip() else []

        total_chunks = 0
        for page in pages:
            chunks = await self.ingester.chunk_text(page["text"], metadata={
                "document_id": document_id,
                "source": page["url"],
                "title": page.get("title", ""),
                "doc_type": "url",
            })
            if chunks:
                count = await self.vector_store.add_documents(collection_name, chunks)
                total_chunks += count

        logger.info("URL ingestion complete",
                     url=url, pages=len(pages), chunks=total_chunks)
        return total_chunks

    async def ingest_api(
        self,
        collection_name: str,
        document_id: str,
        api_url: str,
        method: str = "GET",
        headers: Optional[dict] = None,
        auth_token: Optional[str] = None,
    ) -> int:
        """
        Ingest data from an external API endpoint.

        Returns:
            Number of chunks indexed
        """
        chunks = await self.api_connector.fetch_data(
            url=api_url,
            method=method,
            headers=headers,
            auth_token=auth_token,
        )

        # Add document_id to metadata
        for chunk in chunks:
            chunk["metadata"]["document_id"] = document_id

        if chunks:
            count = await self.vector_store.add_documents(collection_name, chunks)
            return count

        return 0

    # ---- Retrieval Methods ----

    async def retrieve(
        self,
        collection_name: str,
        query: str,
        top_k: int = 5,
        score_threshold: float = 0.3,
    ) -> list[dict]:
        """
        Retrieve relevant chunks for a user query.

        Returns:
            List of relevant chunks with text, score, and metadata
        """
        results = await self.vector_store.search(
            collection_name=collection_name,
            query=query,
            top_k=top_k,
            score_threshold=score_threshold,
        )

        logger.info("RAG retrieval",
                     collection=collection_name,
                     query_length=len(query),
                     results=len(results))
        return results

    async def build_context(
        self,
        collection_name: str,
        query: str,
        top_k: int = 5,
        max_context_length: int = 3000,
    ) -> str:
        """
        Retrieve and format context for LLM consumption.

        Returns:
            Formatted context string
        """
        context, _ = await self.build_context_with_sources(
            collection_name, query, top_k=top_k, max_context_length=max_context_length
        )
        return context

    async def build_context_with_sources(
        self,
        collection_name: str,
        query: str,
        top_k: int = 5,
        max_context_length: int = 3000,
    ) -> tuple[str, list[dict]]:
        """
        Retrieve and format context for LLM consumption — returns both
        the formatted context AND source metadata in a SINGLE embedding call.

        This avoids the expensive pattern of calling build_context() + retrieve()
        separately, which would embed the same query twice (~400ms wasted).

        Args:
            collection_name: Tenant's Qdrant collection
            query: User's question
            top_k: Number of chunks to retrieve
            max_context_length: Maximum character length of context

        Returns:
            Tuple of (formatted_context_string, list_of_source_dicts)
        """
        results = await self.retrieve(collection_name, query, top_k=top_k)

        if not results:
            return "", []

        # Extract sources from results (before truncation)
        sources = [{"source": r.get("source", ""), "score": r["score"]} for r in results]

        context_parts = []
        current_length = 0

        for result in results:
            text = result["text"]
            source = result.get("source", "")

            # Build context entry
            entry = f"[Quelle: {source}]\n{text}"

            if current_length + len(entry) > max_context_length:
                break

            context_parts.append(entry)
            current_length += len(entry)

        context = "\n\n---\n\n".join(context_parts)
        logger.info("Context built (with sources)",
                     collection=collection_name,
                     chunks_used=len(context_parts),
                     context_length=len(context),
                     sources_count=len(sources))
        return context, sources

    # ---- Cleanup Methods ----

    async def delete_document(self, collection_name: str, document_id: str):
        """Remove all chunks for a specific document."""
        await self.vector_store.delete_document(collection_name, document_id)

    async def delete_collection(self, collection_name: str):
        """Delete an entire tenant's knowledge base."""
        await self.vector_store.delete_collection(collection_name)

    async def close(self):
        # NOTE: Do NOT close vector_store — it's a shared singleton.
        await self.crawler.close()
        await self.api_connector.close()
