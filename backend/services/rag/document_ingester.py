"""
Document Ingestion Service.

Handles:
- File upload (PDF, DOCX, TXT, CSV)
- Text extraction
- Chunking (splitting into manageable pieces)
- Embedding and storage in vector DB
"""

from typing import Optional
from pathlib import Path
import structlog

from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = structlog.get_logger()


class DocumentIngester:
    """Processes documents into chunks for RAG."""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    async def extract_text(self, file_path: str, doc_type: str) -> str:
        """Extract text content from a document file."""

        if doc_type == "pdf":
            return await self._extract_pdf(file_path)
        elif doc_type == "docx":
            return await self._extract_docx(file_path)
        elif doc_type == "txt":
            return await self._extract_txt(file_path)
        elif doc_type == "csv":
            return await self._extract_csv(file_path)
        else:
            raise ValueError(f"Unsupported document type: {doc_type}")

    async def chunk_text(
        self,
        text: str,
        metadata: Optional[dict] = None,
    ) -> list[dict]:
        """
        Split text into chunks for embedding.

        Returns list of dicts with 'text' and 'metadata' keys.
        """
        chunks = self.text_splitter.split_text(text)
        base_metadata = metadata or {}

        return [
            {
                "text": chunk,
                "metadata": {
                    **base_metadata,
                    "chunk_index": i,
                    "chunk_total": len(chunks),
                },
            }
            for i, chunk in enumerate(chunks)
        ]

    async def process_document(
        self,
        file_path: str,
        doc_type: str,
        document_id: str,
        source_name: str,
    ) -> list[dict]:
        """
        Full pipeline: Extract text → chunk → prepare for embedding.

        Returns chunks ready to be stored in the vector DB.
        """
        logger.info("Processing document", file=file_path, type=doc_type)

        text = await self.extract_text(file_path, doc_type)

        if not text.strip():
            logger.warning("Empty document", file=file_path)
            return []

        chunks = await self.chunk_text(text, metadata={
            "document_id": document_id,
            "source": source_name,
            "doc_type": doc_type,
        })

        logger.info("Document processed",
                     file=file_path, chunks=len(chunks), chars=len(text))
        return chunks

    async def _extract_pdf(self, file_path: str) -> str:
        """Extract text from PDF using pypdf."""
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        texts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                texts.append(text)
        return "\n\n".join(texts)

    async def _extract_docx(self, file_path: str) -> str:
        """Extract text from DOCX."""
        from docx import Document

        doc = Document(file_path)
        texts = [para.text for para in doc.paragraphs if para.text.strip()]
        return "\n\n".join(texts)

    async def _extract_txt(self, file_path: str) -> str:
        """Extract text from plain text file."""
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    async def _extract_csv(self, file_path: str) -> str:
        """Extract text from CSV, converting rows to readable format."""
        import csv

        texts = []
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row_text = " | ".join(f"{k}: {v}" for k, v in row.items() if v)
                texts.append(row_text)
        return "\n".join(texts)
