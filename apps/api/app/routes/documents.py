"""Document ingestion routes: upload and list documents."""

from fastapi import APIRouter, File, UploadFile

from app.models.document import Document
from app.services import ingestion

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=Document, status_code=201)
async def upload_document(file: UploadFile = File(...)) -> Document:
    """Accept a PDF or text upload, extract its text, and store metadata."""
    return await ingestion.ingest_upload(file)


@router.get("", response_model=list[Document])
def list_documents() -> list[Document]:
    """List documents ingested into local metadata storage."""
    return ingestion.list_documents()
