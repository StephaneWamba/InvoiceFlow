# Tech Stack - Document Matching & Reconciliation

## Backend

**Framework**: FastAPI (Python)

- Fast async processing for document uploads
- Built-in OpenAPI docs
- Easy PDF/DOCX handling

**Package Manager**: `uv`

- Fast dependency resolution and installation
- Optimized for Docker builds

**Document Intelligence**:

- **Primary**: Azure Form Recognizer (pre-built invoice/PO models)
- Pre-trained models for invoices, purchase orders, receipts

**Database**: PostgreSQL

- Workspace storage, extracted data, matching results
- Production-ready from start

**PDF Processing**:

- **PyMuPDF** (fitz) for text extraction and PDF manipulation
- `python-docx` for DOCX
- `reportlab` for PDF report generation

**Matching Engine**: Pure Python

- Fuzzy matching for PO numbers/vendor names (rapidfuzz)
- Line item comparison logic

**File Storage**: S3/MinIO

- Production-ready object storage
- Temporary document storage per workspace

## Frontend

**Framework**: Next.js 14+ (React)

- Server components for faster loads
- File upload with progress
- Real-time status updates

**UI Library**: shadcn/ui + Tailwind CSS

- Table components for comparisons
- Drag & drop file upload
- Color-coded status indicators

**State**: Zustand or React Query

- Workspace management
- Document processing state

## Infrastructure

**Deployment**: Docker Compose

- Optimized Dockerfiles for faster builds
- Multi-stage builds with layer caching
- Backend + Frontend + PostgreSQL + MinIO containers

## Test Data Sources

1. **Synthetic PDF Generation**:

   - Generate realistic PO/Invoice/Delivery Note PDFs using `reportlab`
   - Create test cases with various mismatch scenarios

2. **Public Datasets**:

   - **Kaggle**: Search "invoice dataset" or "purchase order dataset"
   - **GitHub**: `invoice-parser` repos often have sample PDFs
   - **DocBank**: Document understanding datasets

3. **Template Generators**:

   - Use invoice/PO templates from:
     - Invoice template websites (export as PDF)
     - Accounting software demos (QuickBooks, Xero trial accounts)
     - Create variations manually

4. **Realistic Test Cases**:
   - Generate 10-20 document sets with:
     - Perfect matches
     - Quantity mismatches
     - Price changes
     - Missing items
     - Extra items
     - Vendor name variations

## Missing Considerations

1. **Error Handling**: What if document extraction fails? Retry logic?
2. **File Size Limits**: 100 pages max - enforce upload limits
3. **Processing Timeout**: Set max processing time per document
4. **Data Validation**: Validate extracted data before matching
5. **Workspace Cleanup**: Auto-delete temporary workspaces after X hours
6. **Export Formats**: JSON/CSV export implementation details
7. **Browser Compatibility**: Test file upload on different browsers
8. **Concurrent Processing**: Handle multiple document uploads simultaneously
9. **Extraction Confidence**: Show confidence scores for extracted fields
10. **Manual Override**: Allow users to correct extracted data before matching
