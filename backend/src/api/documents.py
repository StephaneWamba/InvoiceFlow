from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from typing import List

from src.core.database import get_db
from src.models.document import Document, DocumentType

router = APIRouter()


@router.post("/upload")
async def upload_document(
    workspace_id: str,
    document_type: DocumentType,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a document"""
    # TODO: Implement file upload to MinIO
    # TODO: Implement document processing
    return {"message": "Upload endpoint - to be implemented"}


@router.get("/workspace/{workspace_id}")
async def list_documents(workspace_id: str, db: Session = Depends(get_db)):
    """List all documents in a workspace"""
    documents = db.query(Document).filter(Document.workspace_id == workspace_id).all()
    return documents


@router.get("/{document_id}")
async def get_document(document_id: str, db: Session = Depends(get_db)):
    """Get a document by ID"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document

