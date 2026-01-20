from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import settings
from src.api import workspaces, documents, matching, reports, extracted_data

app = FastAPI(
    title="InvoiceFlow API",
    description="Document Matching & Reconciliation Platform",
    version="0.1.0",
    redirect_slashes=False,  # Disable automatic trailing slash redirects
)

# CORS middleware
# Parse CORS_ORIGINS: "*" for all origins, or comma-separated list
# Handle cases where value might be a JSON-like string or plain string
cors_origins_value = settings.CORS_ORIGINS.strip()

# Remove brackets if present (e.g., '["http://localhost:3100"]' -> '"http://localhost:3100"')
if cors_origins_value.startswith("[") and cors_origins_value.endswith("]"):
    cors_origins_value = cors_origins_value[1:-1].strip()

# Remove quotes if present
if cors_origins_value.startswith('"') and cors_origins_value.endswith('"'):
    cors_origins_value = cors_origins_value[1:-1].strip()
elif cors_origins_value.startswith("'") and cors_origins_value.endswith("'"):
    cors_origins_value = cors_origins_value[1:-1].strip()

if cors_origins_value == "*":
    cors_origins = ["*"]
    allow_credentials = False  # Can't use credentials with "*"
else:
    cors_origins = [origin.strip().strip('"').strip("'") for origin in cors_origins_value.split(",")]
    allow_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],  # FastAPI recommends "*" - includes OPTIONS automatically
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,  # Cache preflight requests for 1 hour
)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "InvoiceFlow API", "version": "0.1.0"}


# Include routers
app.include_router(workspaces.router, prefix="/api/workspaces", tags=["workspaces"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(extracted_data.router, prefix="/api/extracted-data", tags=["extracted-data"])
app.include_router(matching.router, prefix="/api/matching", tags=["matching"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])



