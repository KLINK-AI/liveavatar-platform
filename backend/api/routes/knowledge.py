"""
Knowledge Base API Routes — Manage RAG data sources.

Endpoints:
- POST /                     → Create a knowledge base
- GET  /                     → List knowledge bases
- POST /{kb_id}/documents    → Upload a document
- POST /{kb_id}/urls         → Index a URL/website
- POST /{kb_id}/apis         → Connect an API source
- GET  /{kb_id}/documents    → List documents
- DELETE /{kb_id}/documents/{doc_id} → Remove a document
- POST /{kb_id}/search       → Test search against KB
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import os
import uuid

from database import get_db
from models.tenant import Tenant
from models.knowledge_base import KnowledgeBase, Document, DocumentType, DocumentStatus
from api.middleware.auth import get_current_tenant
from services.rag.pipeline import RAGPipeline
from services.llm.provider_factory import LLMProviderFactory
from services.llm.base import LLMMessage
import structlog

logger = structlog.get_logger()
router = APIRouter()


class CreateKBRequest(BaseModel):
    name: str
    description: Optional[str] = None


class IndexURLRequest(BaseModel):
    url: str
    name: Optional[str] = None
    crawl_site: bool = False
    max_pages: int = 20


class IndexAPIRequest(BaseModel):
    name: str
    url: str
    method: str = "GET"
    headers: Optional[dict] = None
    auth_token: Optional[str] = None


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    generate_answer: bool = True


@router.post("/")
async def create_knowledge_base(
    request: CreateKBRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Create a new knowledge base for the tenant."""
    collection_name = f"kb_{tenant.slug}_{uuid.uuid4().hex[:8]}"

    kb = KnowledgeBase(
        tenant_id=tenant.id,
        name=request.name,
        description=request.description,
        qdrant_collection=collection_name,
    )
    db.add(kb)
    await db.flush()

    # Ensure Qdrant collection exists
    rag = RAGPipeline()
    await rag.vector_store.ensure_collection(collection_name)
    await rag.close()

    return {
        "id": kb.id,
        "name": kb.name,
        "collection": kb.qdrant_collection,
        "created_at": kb.created_at.isoformat(),
    }


@router.get("/")
async def list_knowledge_bases(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List all knowledge bases for the tenant."""
    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.tenant_id == tenant.id)
    )
    kbs = result.scalars().all()
    return [
        {
            "id": kb.id,
            "name": kb.name,
            "description": kb.description,
            "document_count": len(kb.documents) if kb.documents else 0,
            "created_at": kb.created_at.isoformat(),
        }
        for kb in kbs
    ]


@router.post("/{kb_id}/documents")
async def upload_document(
    kb_id: str,
    file: UploadFile = File(...),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Upload and index a document (PDF, DOCX, TXT, CSV)."""
    kb = await _get_kb(kb_id, tenant.id, db)

    # Determine document type
    ext = os.path.splitext(file.filename or "")[1].lower().lstrip(".")
    if ext not in ("pdf", "docx", "txt", "csv"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: .{ext}. Supported: pdf, docx, txt, csv"
        )

    doc_type = DocumentType(ext)

    # Save file
    doc_id = str(uuid.uuid4())
    upload_dir = f"/app/uploads/{tenant.slug}"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = f"{upload_dir}/{doc_id}_{file.filename}"

    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Create document record
    doc = Document(
        knowledge_base_id=kb.id,
        name=file.filename or "unknown",
        doc_type=doc_type,
        file_path=file_path,
        status=DocumentStatus.PROCESSING,
    )
    db.add(doc)
    await db.flush()

    # Index document
    rag = RAGPipeline()
    try:
        chunk_count = await rag.ingest_document(
            collection_name=kb.qdrant_collection,
            file_path=file_path,
            doc_type=ext,
            document_id=doc.id,
            source_name=file.filename or "upload",
        )
        doc.status = DocumentStatus.INDEXED
        doc.chunk_count = chunk_count
    except Exception as e:
        doc.status = DocumentStatus.ERROR
        doc.error_message = str(e)
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")
    finally:
        await rag.close()

    return {
        "id": doc.id,
        "name": doc.name,
        "status": doc.status.value,
        "chunks": doc.chunk_count,
    }


@router.post("/{kb_id}/urls")
async def index_url(
    kb_id: str,
    request: IndexURLRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Index a URL or crawl a website into the knowledge base."""
    kb = await _get_kb(kb_id, tenant.id, db)

    doc_id = str(uuid.uuid4())
    doc = Document(
        id=doc_id,
        knowledge_base_id=kb.id,
        name=request.name or request.url,
        doc_type=DocumentType.URL,
        source_url=request.url,
        status=DocumentStatus.PROCESSING,
    )
    db.add(doc)
    await db.flush()

    rag = RAGPipeline()
    try:
        chunk_count = await rag.ingest_url(
            collection_name=kb.qdrant_collection,
            url=request.url,
            document_id=doc.id,
            crawl_site=request.crawl_site,
            max_pages=request.max_pages,
        )
        doc.status = DocumentStatus.INDEXED
        doc.chunk_count = chunk_count
    except Exception as e:
        doc.status = DocumentStatus.ERROR
        doc.error_message = str(e)
        raise HTTPException(status_code=500, detail=f"URL indexing failed: {str(e)}")
    finally:
        await rag.close()

    return {
        "id": doc.id,
        "name": doc.name,
        "url": request.url,
        "status": doc.status.value,
        "chunks": doc.chunk_count,
    }


@router.post("/{kb_id}/apis")
async def index_api(
    kb_id: str,
    request: IndexAPIRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Connect and index an external API as a data source."""
    kb = await _get_kb(kb_id, tenant.id, db)

    doc_id = str(uuid.uuid4())
    doc = Document(
        id=doc_id,
        knowledge_base_id=kb.id,
        name=request.name,
        doc_type=DocumentType.API,
        source_url=request.url,
        status=DocumentStatus.PROCESSING,
        metadata_json={"method": request.method, "headers": request.headers},
    )
    db.add(doc)
    await db.flush()

    rag = RAGPipeline()
    try:
        chunk_count = await rag.ingest_api(
            collection_name=kb.qdrant_collection,
            document_id=doc.id,
            api_url=request.url,
            method=request.method,
            headers=request.headers,
            auth_token=request.auth_token,
        )
        doc.status = DocumentStatus.INDEXED
        doc.chunk_count = chunk_count
    except Exception as e:
        doc.status = DocumentStatus.ERROR
        doc.error_message = str(e)
        raise HTTPException(status_code=500, detail=f"API indexing failed: {str(e)}")
    finally:
        await rag.close()

    return {
        "id": doc.id,
        "name": doc.name,
        "status": doc.status.value,
        "chunks": doc.chunk_count,
    }


@router.get("/{kb_id}/documents")
async def list_documents(
    kb_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List all documents in a knowledge base."""
    kb = await _get_kb(kb_id, tenant.id, db)
    return [
        {
            "id": doc.id,
            "name": doc.name,
            "type": doc.doc_type.value,
            "status": doc.status.value,
            "chunks": doc.chunk_count,
            "source_url": doc.source_url,
            "created_at": doc.created_at.isoformat(),
        }
        for doc in (kb.documents or [])
    ]


@router.delete("/{kb_id}/documents/{doc_id}")
async def delete_document(
    kb_id: str,
    doc_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Remove a document from the knowledge base."""
    kb = await _get_kb(kb_id, tenant.id, db)

    result = await db.execute(
        select(Document).where(
            Document.id == doc_id,
            Document.knowledge_base_id == kb.id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Remove from vector store
    rag = RAGPipeline()
    try:
        await rag.delete_document(kb.qdrant_collection, doc.id)
    finally:
        await rag.close()

    # Remove from DB
    await db.delete(doc)

    return {"status": "deleted", "document_id": doc_id}


@router.delete("/{kb_id}")
async def delete_knowledge_base(
    kb_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Delete a knowledge base and all its documents + Qdrant collection."""
    kb = await _get_kb(kb_id, tenant.id, db)

    # Delete entire Qdrant collection
    rag = RAGPipeline()
    try:
        await rag.delete_collection(kb.qdrant_collection)
    except Exception as e:
        logger.warning("Failed to delete Qdrant collection", collection=kb.qdrant_collection, error=str(e))
    finally:
        await rag.close()

    # Delete all documents from DB
    doc_result = await db.execute(
        select(Document).where(Document.knowledge_base_id == kb.id)
    )
    for doc in doc_result.scalars().all():
        await db.delete(doc)

    # Delete KB record
    await db.delete(kb)

    logger.info("Knowledge base deleted", kb_id=kb_id, tenant=tenant.slug)
    return {"status": "deleted", "kb_id": kb_id, "name": kb.name}


@router.post("/{kb_id}/search")
async def search_knowledge_base(
    kb_id: str,
    request: SearchRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Test search against the knowledge base — returns RAG chunks + optional LLM answer."""
    kb = await _get_kb(kb_id, tenant.id, db)

    rag = RAGPipeline()
    try:
        results = await rag.retrieve(
            collection_name=kb.qdrant_collection,
            query=request.query,
            top_k=request.top_k,
        )
        # Build context string from search results
        context = await rag.build_context(
            collection_name=kb.qdrant_collection,
            query=request.query,
            top_k=request.top_k,
        )
    finally:
        await rag.close()

    response_data = {
        "query": request.query,
        "results": results,
        "count": len(results),
    }

    # Generate LLM answer from the search context
    if request.generate_answer and results:
        try:
            llm = LLMProviderFactory.get_provider_for_tenant(tenant)
            system_prompt = tenant.system_prompt or (
                "Du bist ein hilfreicher Assistent. Beantworte die Frage basierend "
                "auf dem bereitgestellten Kontext. Antworte auf Deutsch, wenn die "
                "Frage auf Deutsch gestellt wird."
            )
            messages = [
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(
                    role="system",
                    content=f"KONTEXT aus der Wissensbasis:\n\n{context}",
                ),
                LLMMessage(role="user", content=request.query),
            ]

            llm_response = await llm.chat(
                messages=messages,
                temperature=0.7,
                max_tokens=800,
            )
            response_data["answer"] = llm_response.content
            response_data["llm_model"] = llm_response.model
            response_data["llm_provider"] = llm_response.provider
        except Exception as e:
            logger.error("llm_answer_generation_failed", error=str(e))
            response_data["answer"] = None
            response_data["answer_error"] = str(e)

    return response_data


async def _get_kb(kb_id: str, tenant_id: str, db: AsyncSession) -> KnowledgeBase:
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.tenant_id == tenant_id,
        )
    )
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return kb
