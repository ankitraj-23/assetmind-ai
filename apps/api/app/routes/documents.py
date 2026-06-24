"""Document ingestion routes: upload and list documents."""

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.models.chunk import DocumentChunks
from app.models.document import Document
from app.models.embedding import DocumentEmbeddings, EmbeddingPreview
from app.services import chunking, embeddings, ingestion

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


@router.get("/{document_id}/embeddings", response_model=DocumentEmbeddings)
def get_document_embeddings(document_id: str) -> DocumentEmbeddings:
    """Return embedding metadata (with short vector previews) for a document."""
    known_ids = {doc.id for doc in ingestion.list_documents()}
    if document_id not in known_ids:
        raise HTTPException(status_code=404, detail="Document not found.")
    records = embeddings.get_embeddings(document_id)
    previews = [
        EmbeddingPreview(
            chunk_id=record.chunk_id,
            document_id=record.document_id,
            chunk_index=record.chunk_index,
            dimension=record.dimension,
            preview=record.vector[: embeddings.PREVIEW_LENGTH],
        )
        for record in records
    ]
    return DocumentEmbeddings(
        document_id=document_id,
        embedding_model=embeddings.EMBEDDING_MODEL,
        dimension=embeddings.EMBEDDING_DIMENSION,
        embeddings=previews,
    )
