from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import settings
from src.api import workspaces, documents, matching, reports, extracted_data

app = FastAPI(
    title="InvoiceFlow API",
    description="Document Matching & Reconciliation Platform",
    version="0.1.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(workspaces.router, prefix="/api/workspaces", tags=["workspaces"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(extracted_data.router, prefix="/api/extracted-data", tags=["extracted-data"])
app.include_router(matching.router, prefix="/api/matching", tags=["matching"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "InvoiceFlow API", "version": "0.1.0"}

