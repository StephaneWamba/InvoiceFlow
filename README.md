# InvoiceFlow - Document Matching & Reconciliation Platform

Automated document matching and three-way reconciliation for Purchase Orders, Invoices, and Delivery Notes.

## Features

- **Document Processing**: Extract structured data from PO, Invoice, and Delivery Note PDFs using Azure Form Recognizer
- **Automatic Matching**: Match documents by PO number or vendor name
- **Line Item Comparison**: Detect quantity mismatches, price changes, missing items
- **Three-Way Reconciliation**: Compare PO ↔ Invoice ↔ Delivery Note
- **Report Generation**: Generate PDF reconciliation reports with discrepancy flags

## Tech Stack

- **Backend**: FastAPI (Python), PostgreSQL, Azure Form Recognizer, PyMuPDF
- **Frontend**: Next.js 14, TypeScript, Tailwind CSS, shadcn/ui
- **Infrastructure**: Docker, MinIO (S3-compatible), PostgreSQL
- **Package Manager**: `uv`

## Quick Start

```bash
# Start all services
docker-compose up

# Backend: http://localhost:8000
# Frontend: http://localhost:3000
# MinIO: http://localhost:9000
```

## Development

See `private/roadmap.md` for detailed development plan.

## Documentation

All project documentation is in the `private/` folder:
- `document-matching-reconciliation.md` - Project specification
- `tech-stack-recommendation.md` - Technology choices
- `roadmap.md` - Development roadmap

