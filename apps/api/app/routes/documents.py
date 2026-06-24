"""Document ingestion routes: upload and list documents."""

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.models.chunk import DocumentChunks
from app.models.document import Document
from app.services import chunking, ingestion

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=Document, status_code=201)
async def upload_document(file: UploadFile = File(...)) -> Document:
    """Accept a PDF or text upload, extract its text, and store metadata."""
    return await ingestion.ingest_upload(file)


@router.get("", response_model=list[Document])
def list_documents() -> list[Document]:
    """List documents ingested into local metadata storage."""
    return ingestion.list_documents()


@router.get("/{document_id}/chunks", response_model=DocumentChunks)
def get_document_chunks(document_id: str) -> DocumentChunks:
    """Return the ordered text chunks for a single document."""
    known_ids = {doc.id for doc in ingestion.list_documents()}
    if document_id not in known_ids:
        raise HTTPException(status_code=404, detail="Document not found.")
    return DocumentChunks(
        document_id=document_id,
        chunks=chunking.get_chunks(document_id),
    )
