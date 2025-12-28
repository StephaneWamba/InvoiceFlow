# Document Matching & Reconciliation Platform — Project Specification

**Platform**: PO/Invoice/Delivery Note Matching & Three-Way Reconciliation  
**Created**: 2025-01-27

---

## Overview

A document matching platform for procurement and accounts payable teams. Automatically extracts structured data from Purchase Orders, Invoices, and Delivery Notes, matches documents by PO number or vendor, compares line items, and generates reconciliation reports with discrepancy flags.

**Core Features:**

- Structured data extraction from PO, Invoice, Delivery Note
- Automatic document matching
- Line-item comparison with discrepancy detection
- Three-way reconciliation (PO ↔ Invoice ↔ Delivery Note)
- Reconciliation report generation

---

## User Journey

### Journey: Procurement/Invoice Matching & Reconciliation

**User**: Procurement Team / Accounts Payable

**Goal**: Match PO, Invoice, and Delivery Note; identify discrepancies

**Steps**:

1. **Upload Documents**

   - Upload Purchase Order (PDF)
   - Upload Invoice (PDF)
   - Upload Delivery Note (PDF, optional)
   - System: "Processing documents... Extracting data"

2. **View Extracted Data**

   - System shows extracted fields:
     - **PO Number**: PO-2025-001
     - **Vendor**: ABC Supplies Inc.
     - **Items**: [Table view with quantities, prices, descriptions]
     - **Total**: $12,450.00
     - **Date**: 2025-01-15

3. **Automatic Matching**

   - System matches documents by PO number
   - Status: "PO-2025-001 ↔ Invoice IN-7892 ↔ Delivery Note DN-456"
   - Matching indicators: ✅ Matched / ⚠️ Mismatch / ❌ Missing

4. **Review Mismatches**

   - Mismatch panel highlights:
     - ⚠️ **Quantity Mismatch**: Item #3 ordered 50 units, invoice shows 52 units
     - ⚠️ **Price Change**: Item #5 price increased from $120 → $125
     - ❌ **Missing Item**: Item #8 on PO not found on invoice
     - ✅ **Matched**: Items #1, #2, #4, #6, #7 match correctly
   - Click mismatch → View side-by-side comparison

5. **Three-Way Reconciliation**

   - System compares PO ↔ Invoice ↔ Delivery Note
   - Shows:
     - Items delivered (delivery note)
     - Items invoiced (invoice)
     - Items ordered (PO)
   - Highlights: Over-delivery, under-delivery, invoiced but not delivered

6. **Generate Report**
   - Click "Generate Reconciliation Report"
   - PDF report includes:
     - Executive summary (total matched, mismatches, exceptions)
     - Item-by-item comparison table
     - Mismatch details with evidence
     - Approval workflow (if configured)

**Time Saved**: 1-2 hours → 5 minutes per reconciliation

---

## Project Scope & Data Boundaries

### Data Isolation & Scoping

**How documents are isolated:**

- Each user session creates a **workspace** (temporary or saved)
- All documents uploaded in a workspace belong only to that workspace
- Workspaces are completely separate — no cross-contamination
- Switching workspaces shows different document sets
- Each workspace processes independently

**Document set boundaries:**

- **Document Matching**: One matching group per session (PO + Invoice + Delivery Note grouped together)
- Each matching group is processed independently
- Users can create multiple workspaces for different reconciliation batches

**What happens when uploading:**

- Uploading to Workspace A does not affect Workspace B
- Processing in one workspace does not slow down or interfere with another
- Each workspace processes independently
- Results are stored per workspace, not globally

---

### In Scope (DO)

**Document Matching:**

- Extract structured data from PO, Invoice, Delivery Note
- Extract fields: PO number, invoice number, vendor name, dates, totals
- Extract line items: item descriptions, quantities, unit prices, line totals
- Match documents by PO number or vendor name
- Compare line items (quantities, prices, descriptions)
- Flag mismatches and missing items
- Generate reconciliation reports

**Comparison Features:**

- Side-by-side comparison view for mismatched items
- Three-way reconciliation (PO ↔ Invoice ↔ Delivery Note)
- Summary totals comparison
- Discrepancy categorization (quantity mismatch, price change, missing item, extra item)

**Export & Reporting:**

- Generate PDF reconciliation reports
- Export comparison data (JSON, CSV)
- Include evidence (extracted data, mismatch highlights)

**General:**

- Support PDF and DOCX formats
- Process documents up to 100 pages each
- Store results per workspace (temporary or saved)
- Basic error handling and retry for failed uploads

---

### Out of Scope (DON'T)

**Document Matching:**

- Automatic approval workflows
- Integration with accounting systems (ERP, QuickBooks, SAP, etc.)
- Payment processing or invoice payment
- Vendor management features
- Historical trend analysis across multiple periods
- Batch processing of multiple PO/invoice pairs simultaneously

**Advanced Features:**

- OCR for handwritten documents
- Automatic discrepancy resolution suggestions
- Multi-currency support (USD only for MVP)
- Tax calculation and comparison
- Discount and promotion code handling

**General:**

- User authentication or multi-user accounts (single-user MVP)
- Document versioning or change tracking
- Advanced OCR for handwritten text or poor-quality scans
- Support for Excel, PowerPoint, or image-only files
- API access or third-party integrations
- Mobile app (web-only)
- Offline mode
- Document storage beyond session/workspace lifetime (unless explicitly saved)

---

### Data Boundaries Summary

**Per Workspace:**

- Documents uploaded (PO, Invoice, Delivery Note)
- Extracted structured data
- Matching results
- Comparison results
- Generated reports

**Not Shared:**

- Workspaces are isolated from each other
- No global document library (unless user explicitly saves/imports)
- No cross-workspace matching or analysis
- Each workspace is independent

**Data Lifecycle:**

- Temporary workspaces: Deleted when browser session ends
- Saved workspaces: Persist until user deletes them
- No automatic data retention beyond user control

---

## Concrete User Journey Example

### Example: Accounts Payable Matching Purchase Order with Invoice

**User**: Jennifer Kim, Accounts Payable Specialist at Manufacturing Corp

**Scenario**: Jennifer receives Invoice #INV-2025-0042 from supplier SteelWorks Inc. She needs to verify it matches Purchase Order #PO-2025-0189 and Delivery Note #DN-7892 before approving payment.

**Steps**:

1. Jennifer creates workspace "PO-2025-0189 Reconciliation"
2. Uploads three documents:
   - `PO-2025-0189-SteelWorks.pdf`
   - `Invoice-INV-2025-0042-SteelWorks.pdf`
   - `DeliveryNote-DN-7892-SteelWorks.pdf`
3. System: "Processing documents... Extracting data... Matching by PO number..."
4. **Extracted Data**:
   - PO Number: PO-2025-0189
   - Vendor: SteelWorks Inc.
   - Invoice Number: INV-2025-0042
   - Delivery Note: DN-7892
5. **Matching Results**:
   - ✅ PO Number matches across all documents
   - ✅ Vendor name matches: "SteelWorks Inc."
   - ✅ Invoice date (2025-01-20) matches delivery date
6. **Line Item Comparison**:
   - ✅ Item #1: "Steel Sheets 10mm x 100 sheets" - Quantity: 100, Price: $45.00/unit - **MATCHED** across all 3 documents
   - ✅ Item #2: "Steel Beams 20cm x 50 units" - Quantity: 50, Price: $120.00/unit - **MATCHED**
   - ⚠️ Item #3: "Steel Bolts M12 x 500 units" - PO: 500 units @ $2.50, Invoice: 520 units @ $2.50, Delivery: 520 units - **QUANTITY MISMATCH** (20 extra units invoiced and delivered)
   - ⚠️ Item #4: "Welding Wire 5kg spools x 10" - PO: 10 @ $85.00, Invoice: 10 @ $90.00, Delivery: 10 - **PRICE INCREASE** ($5.00 per unit increase)
   - ✅ Item #5: "Safety Equipment Kit x 5" - Quantity: 5, Price: $250.00/kit - **MATCHED**
7. Jennifer clicks on Item #3 mismatch: Side-by-side view shows PO ordered 500, but 520 were delivered and invoiced
8. Jennifer clicks on Item #4 mismatch: Price changed from $85 to $90 per unit (5.9% increase)
9. **Summary Panel**:
   - Total PO Value: $10,925.00
   - Total Invoice Value: $11,075.00
   - Difference: +$150.00 (overcharge)
   - Mismatches: 2 items require attention
10. Jennifer generates reconciliation report (PDF)
11. Report includes: Executive summary, item-by-item table, mismatch details with evidence, approval notes section
12. Jennifer adds note: "Quantity variance approved - supplier included extras. Price increase needs approval from procurement manager."
13. Emails report to procurement manager for approval on price increase

**Outcome**: Three-way reconciliation completed in 4 minutes. Identified $150 overcharge and 2 discrepancies that require approval. (Manual reconciliation would take 45-60 minutes)

---

## Common UI Patterns

### Document Upload

- Clear sections for PO, Invoice, Delivery Note (optional)
- Drag & drop or file browser
- Progress indicator during processing

### Comparison View

- Side-by-side layout: PO | Invoice | Delivery Note
- Color-coded matching status (green = matched, yellow = mismatch, red = missing)
- Click item → Detailed comparison view

### Mismatch Panel

- List of all mismatches with severity
- Filter by type (quantity, price, missing item)
- Click to view detailed side-by-side comparison

### Report Generation

- One-click PDF generation
- Preview before download
- Includes all extracted data, comparisons, and notes

### Status & Progress

- Real-time processing status
- Estimated time remaining
- Error handling with retry options

---

**Last Updated**: 2025-01-27
