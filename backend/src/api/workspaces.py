from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import delete
from pydantic import BaseModel, field_serializer
from typing import List
from datetime import datetime
import logging

from src.core.database import get_db
from src.models.workspace import Workspace
from src.models.document import Document
from src.models.matching import MatchingResult
from src.models.extracted_data import ExtractedData
from src.services.storage import storage_service

logger = logging.getLogger(__name__)

router = APIRouter()


class WorkspaceCreate(BaseModel):
    name: str
    is_temporary: bool = True


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    is_temporary: bool
    created_at: datetime
    updated_at: datetime

    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, dt: datetime) -> str:
        return dt.isoformat() if dt else None

    class Config:
        from_attributes = True


@router.post("/", response_model=WorkspaceResponse)
async def create_workspace(workspace: WorkspaceCreate, db: Session = Depends(get_db)):
    """Create a new workspace"""
    db_workspace = Workspace(name=workspace.name, is_temporary=workspace.is_temporary)
    db.add(db_workspace)
    db.commit()
    db.refresh(db_workspace)
    return db_workspace


@router.get("/", response_model=List[WorkspaceResponse])
async def list_workspaces(db: Session = Depends(get_db)):
    """List all workspaces"""
    workspaces = db.query(Workspace).all()
    return workspaces


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(workspace_id: str, db: Session = Depends(get_db)):
    """Get a workspace by ID"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


@router.delete("/{workspace_id}")
async def delete_workspace(workspace_id: str, db: Session = Depends(get_db)):
    """Delete a workspace and all associated data"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    try:
        # Step 1: Get all documents in this workspace
        documents = db.query(Document).filter(Document.workspace_id == workspace_id).all()
        document_ids = [doc.id for doc in documents]
        
        # Step 2: Delete all document files from storage
        storage_errors = []
        for document in documents:
            try:
                if document.file_path:
                    storage_service.delete_file(document.file_path)
                    logger.info(f"Deleted file from storage: {document.file_path}")
            except Exception as e:
                # Log error but continue - don't fail entire deletion if storage fails
                storage_errors.append(f"Failed to delete file {document.file_path}: {str(e)}")
                logger.warning(f"Failed to delete file {document.file_path} from storage: {str(e)}")
        
        # Step 3: Delete extracted_data explicitly BEFORE deleting documents
        # This prevents the NOT NULL constraint violation
        deleted_extracted_data = 0
        if document_ids:
            deleted_extracted_data = db.query(ExtractedData).filter(
                ExtractedData.document_id.in_(document_ids)
            ).delete(synchronize_session=False)
            logger.info(f"Deleted {deleted_extracted_data} extracted_data records")
        
        # Step 4: Delete matching results for this workspace
        matching_results = db.query(MatchingResult).filter(MatchingResult.workspace_id == workspace_id).all()
        for result in matching_results:
            db.delete(result)
        
        # Step 5: Delete documents explicitly (extracted_data already deleted)
        for document in documents:
            db.delete(document)
        
        # Step 6: Delete the workspace
        db.delete(workspace)
        db.commit()
        
        # Log any storage errors but don't fail the request
        if storage_errors:
            logger.warning(f"Workspace {workspace_id} deleted, but some storage files failed to delete: {storage_errors}")
        
        return {
            "message": "Workspace deleted successfully",
            "deleted_documents": len(documents),
            "deleted_extracted_data": deleted_extracted_data,
            "deleted_matching_results": len(matching_results),
            "storage_warnings": storage_errors if storage_errors else None
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete workspace {workspace_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete workspace: {str(e)}"
        )

