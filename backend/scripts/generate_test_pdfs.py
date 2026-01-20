"""
Generate realistic test PDF sets with real-world company names.
All documents are 1 page long and test all analysis features.
Files are prefixed with enterprise name and total less than 10 files.
"""
from pathlib import Path
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT

# Create realistic test sets directory
# Assets is mounted at /app/assets in Docker (from docker-compose.yml)
import os
if os.path.exists("/app") and os.path.isdir("/app"):
    # Docker environment
    ASSETS_DIR = Path("/app") / "assets" / "test-sets"
else:
    # Local environment
    script_dir = Path(__file__).parent  # scripts/
    backend_dir = script_dir.parent     # backend/
    project_root = backend_dir.parent  # project root
    ASSETS_DIR = project_root / "assets" / "test-sets"

# Create directory, handling case where parent might be a file
try:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
except (FileExistsError, PermissionError) as e:
    # If assets is a file, create in a different location
    if os.path.exists("/app"):
        ASSETS_DIR = Path("/app") / "test-sets"
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    else:
        raise


def generate_invoice(
    invoice_number: str, po_number: str, vendor: str, output_path: Path,
    items: list, currency_code: str = "USD", tax_rate: float = 0.08
):
    """Generate invoice with specific currency and tax rate."""
    doc = SimpleDocTemplate(str(output_path), pagesize=letter)
    story = []
    styles = getSampleStyleSheet()

    # Currency symbol mapping
    currency_symbols = {
        "USD": "$",
        "EUR": "€",
        "GBP": "£",
        "JPY": "¥",
        "CAD": "C$",
        "AUD": "A$",
    }
    symbol = currency_symbols.get(currency_code, currency_code)

    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=30,
    )
    story.append(Paragraph("INVOICE", title_style))
    story.append(Spacer(1, 0.2*inch))

    # Header info
    header_data = [
        ['Invoice Number:', invoice_number, 'Date:',
            datetime.now().strftime('%Y-%m-%d')],
        ['PO Number:', po_number, 'Due Date:',
            (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')],
        ['Currency:', currency_code, 'Payment Terms:', 'Net 30'],
    ]
    header_table = Table(header_data, colWidths=[
                         1.5*inch, 2*inch, 1.5*inch, 2*inch])
    header_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.grey),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 0.3*inch))

    # Vendor and Bill To
    from_para = Paragraph(
        f'<b>{vendor}</b><br/>123 Business St<br/>New York, NY 10001<br/>USA',
        styles['Normal']
    )
    bill_to_para = Paragraph(
        '<b>ACME Corporation</b><br/>456 Customer Ave<br/>Los Angeles, CA 90001<br/>USA',
        styles['Normal']
    )
    vendor_data = [
        ['From:', from_para],
        ['Bill To:', bill_to_para],
    ]
    vendor_table = Table(vendor_data, colWidths=[1*inch, 6*inch])
    vendor_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.grey),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(vendor_table)
    story.append(Spacer(1, 0.3*inch))

    # Line items
    table_data = [['Item #', 'Description', 'Qty', 'Unit Price', 'Total']]
    for item in items:
        table_data.append([
            item['item_num'],
            item['description'],
            str(item['qty']),
            f"{symbol}{item['price']:.2f}",
            f"{symbol}{item['total']:.2f}",
        ])

    items_table = Table(table_data, colWidths=[
                        0.8*inch, 3*inch, 0.8*inch, 1.2*inch, 1.2*inch])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a5568')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (2, 1), (4, -1), 'RIGHT'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1),
         [colors.white, colors.HexColor('#f7fafc')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 0.3*inch))

    # Totals
    subtotal = sum(item['total'] for item in items)
    tax = subtotal * tax_rate
    final_total = subtotal + tax

    totals_data = [
        ['Subtotal:', f'{symbol}{subtotal:,.2f}'],
        [f'Tax ({tax_rate*100:.0f}%):', f'{symbol}{tax:,.2f}'],
        ['Amount Due:', f'{symbol}{final_total:,.2f}'],
    ]
    totals_table = Table(totals_data, colWidths=[1*inch, 1.5*inch])
    totals_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#1a1a1a')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    container_table = Table([[totals_table]], colWidths=[7*inch])
    container_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(container_table)

    # Add Amount Due as standalone text for better Azure recognition
    story.append(Spacer(1, 0.1*inch))
    amount_due_style = ParagraphStyle(
        'AmountDue',
        parent=styles['Normal'],
        fontSize=14,
        fontName='Helvetica-Bold',
        alignment=2,  # Right align
        textColor=colors.HexColor('#1a1a1a'),
    )
    story.append(
        Paragraph(f'Amount Due: {symbol}{final_total:,.2f}', amount_due_style))

    doc.build(story)


def generate_po(
    po_number: str, vendor: str, output_path: Path, items: list, currency_code: str = "USD", tax_rate: float = 0.08
):
    """Generate PO with specific currency and tax rate."""
    doc = SimpleDocTemplate(str(output_path), pagesize=letter)
    story = []
    styles = getSampleStyleSheet()

    currency_symbols = {
        "USD": "$",
        "EUR": "€",
        "GBP": "£",
        "JPY": "¥",
        "CAD": "C$",
        "AUD": "A$",
    }
    symbol = currency_symbols.get(currency_code, currency_code)

    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=30,
    )
    story.append(Paragraph("PURCHASE ORDER", title_style))
    story.append(Spacer(1, 0.2*inch))

    # Header info
    header_data = [
        ['PO Number:', po_number, 'Date:', datetime.now().strftime('%Y-%m-%d')],
        ['Currency:', currency_code, 'Payment Terms:', 'Net 30'],
    ]
    header_table = Table(header_data, colWidths=[
                         1.5*inch, 2*inch, 1.5*inch, 2*inch])
    header_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.grey),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 0.3*inch))

    # Vendor and Ship To
    from_para = Paragraph(
        '<b>ACME Corporation</b><br/>456 Customer Ave<br/>Los Angeles, CA 90001<br/>USA',
        styles['Normal']
    )
    vendor_para = Paragraph(
        f'<b>{vendor}</b><br/>123 Business St<br/>New York, NY 10001<br/>USA',
        styles['Normal']
    )
    vendor_data = [
        ['Ship To:', from_para],
        ['Vendor:', vendor_para],
    ]
    vendor_table = Table(vendor_data, colWidths=[1*inch, 6*inch])
    vendor_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.grey),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(vendor_table)
    story.append(Spacer(1, 0.3*inch))

    # Line items
    table_data = [['Item #', 'Description', 'Qty', 'Unit Price', 'Total']]
    for item in items:
        table_data.append([
            item['item_num'],
            item['description'],
            str(item['qty']),
            f"{symbol}{item['price']:.2f}",
            f"{symbol}{item['total']:.2f}",
        ])

    items_table = Table(table_data, colWidths=[
                        0.8*inch, 3*inch, 0.8*inch, 1.2*inch, 1.2*inch])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a5568')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (2, 1), (4, -1), 'RIGHT'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1),
         [colors.white, colors.HexColor('#f7fafc')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 0.3*inch))

    # Totals
    subtotal = sum(item['total'] for item in items)
    tax = subtotal * tax_rate
    final_total = subtotal + tax

    totals_data = [
        ['Subtotal:', f'{symbol}{subtotal:,.2f}'],
        [f'Tax ({tax_rate*100:.0f}%):', f'{symbol}{tax:,.2f}'],
        ['Total Amount:', f'{symbol}{final_total:,.2f}'],
    ]
    totals_table = Table(totals_data, colWidths=[1*inch, 1.5*inch])
    totals_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#1a1a1a')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    container_table = Table([[totals_table]], colWidths=[7*inch])
    container_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(container_table)

    doc.build(story)


def generate_delivery_note(
    dn_number: str, po_number: str, vendor: str, output_path: Path, items: list
):
    """Generate delivery note (no currency/tax, just quantities)."""
    doc = SimpleDocTemplate(str(output_path), pagesize=letter)
    story = []
    styles = getSampleStyleSheet()

    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=30,
    )
    story.append(Paragraph("DELIVERY NOTE", title_style))
    story.append(Spacer(1, 0.2*inch))

    # Header info
    header_data = [
        ['DN Number:', dn_number, 'Date:', datetime.now().strftime('%Y-%m-%d')],
        ['PO Number:', po_number, 'Delivery Date:',
            datetime.now().strftime('%Y-%m-%d')],
    ]
    header_table = Table(header_data, colWidths=[
                         1.5*inch, 2*inch, 1.5*inch, 2*inch])
    header_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.grey),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 0.3*inch))

    # From and Ship To
    from_para = Paragraph(
        f'<b>{vendor}</b><br/>123 Business St<br/>New York, NY 10001<br/>USA',
        styles['Normal']
    )
    ship_to_para = Paragraph(
        '<b>ACME Corporation</b><br/>456 Customer Ave<br/>Los Angeles, CA 90001<br/>USA',
        styles['Normal']
    )
    vendor_data = [
        ['From:', from_para],
        ['Ship To:', ship_to_para],
    ]
    vendor_table = Table(vendor_data, colWidths=[1*inch, 6*inch])
    vendor_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.grey),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(vendor_table)
    story.append(Spacer(1, 0.3*inch))

    # Line items (no prices for delivery notes)
    table_data = [['Item #', 'Description', 'Quantity']]
    for item in items:
        table_data.append([
            item['item_num'],
            item['description'],
            str(item['qty']),
        ])

    items_table = Table(table_data, colWidths=[0.8*inch, 4.5*inch, 1.2*inch])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a5568')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (2, 1), (2, -1), 'RIGHT'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1),
         [colors.white, colors.HexColor('#f7fafc')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(items_table)

    doc.build(story)


def get_enterprise_prefix(company_name: str) -> str:
    """Convert company name to filename-safe prefix."""
    # Remove common suffixes
    prefix = company_name
    for suffix in [" Inc", " Ltd", " Co", " Corp", " Corporation"]:
        if prefix.endswith(suffix):
            prefix = prefix[:-len(suffix)]
            break
    # Remove spaces and special chars, keep only alphanumeric
    prefix = "".join(c for c in prefix if c.isalnum())
    return prefix


def main():
    """Generate realistic test PDF sets with enterprise-prefixed filenames (< 10 files)."""
    print("Generating realistic test PDF sets with enterprise prefixes...")
    print(f"Output directory: {ASSETS_DIR}\n")
    generated_files = []

    # Scenario 1: Perfect Match (PO + Invoice + Delivery Note)
    print("[Scenario 1] Perfect Match - Complete Set (PO + Invoice + DN)")
    company = "Acme Corporation"
    prefix = get_enterprise_prefix(company)
    po_number = "PO-2024-001"
    invoice_number = "INV-2024-001"
    dn_number = "DN-2024-001"

    items = [
        {'item_num': '001', 'description': 'Product A',
            'qty': 10, 'price': 100.0, 'total': 1000.0},
        {'item_num': '002', 'description': 'Product B',
            'qty': 5, 'price': 200.0, 'total': 1000.0},
    ]

    po_file = ASSETS_DIR / f"{prefix}_po.pdf"
    generate_po(po_number, company, po_file, items, "USD", 0.08)
    generated_files.append(po_file.name)
    print(f"  [OK] Generated: {po_file.name}")

    invoice_file = ASSETS_DIR / f"{prefix}_invoice.pdf"
    generate_invoice(invoice_number, po_number, company,
                     invoice_file, items, "USD", 0.08)
    generated_files.append(invoice_file.name)
    print(f"  [OK] Generated: {invoice_file.name}")

    dn_file = ASSETS_DIR / f"{prefix}_delivery-note.pdf"
    generate_delivery_note(dn_number, po_number, company, dn_file, items)
    generated_files.append(dn_file.name)
    print(f"  [OK] Generated: {dn_file.name}")

    # Scenario 2: Tax Rate Mismatch (PO + Invoice)
    print("\n[Scenario 2] Tax Rate Mismatch - Intentional Discrepancy")
    company = "Metro Supply Chain Solutions"
    prefix = get_enterprise_prefix(company)
    po_number = "PO-2024-002"
    invoice_number = "INV-2024-002"

    items = [
        {'item_num': '001', 'description': 'Item A',
            'qty': 15, 'price': 80.0, 'total': 1200.0},
        {'item_num': '002', 'description': 'Item B',
            'qty': 8, 'price': 150.0, 'total': 1200.0},
    ]

    po_file = ASSETS_DIR / f"{prefix}_po.pdf"
    generate_po(po_number, company, po_file, items, "USD", 0.08)
    generated_files.append(po_file.name)
    print(f"  [OK] Generated: {po_file.name}")

    invoice_file = ASSETS_DIR / f"{prefix}_invoice.pdf"
    generate_invoice(invoice_number, po_number, company,
                     invoice_file, items, "USD", 0.10)  # Different tax rate
    generated_files.append(invoice_file.name)
    print(f"  [OK] Generated: {invoice_file.name}")

    # Scenario 3: Currency Mismatch (PO + Invoice)
    print("\n[Scenario 3] Currency Mismatch - Intentional Discrepancy")
    company = "Worldwide Distribution Corp"
    prefix = get_enterprise_prefix(company)
    po_number = "PO-2024-003"
    invoice_number = "INV-2024-003"

    items = [
        {'item_num': '001', 'description': 'International Item',
            'qty': 12, 'price': 100.0, 'total': 1200.0},
    ]

    po_file = ASSETS_DIR / f"{prefix}_po.pdf"
    generate_po(po_number, company, po_file, items, "USD", 0.08)
    generated_files.append(po_file.name)
    print(f"  [OK] Generated: {po_file.name}")

    invoice_file = ASSETS_DIR / f"{prefix}_invoice.pdf"
    generate_invoice(invoice_number, po_number, company,
                     invoice_file, items, "EUR", 0.20)  # Different currency
    generated_files.append(invoice_file.name)
    print(f"  [OK] Generated: {invoice_file.name}")

    print("\n" + "="*60)
    print("All realistic test PDFs generated successfully!")
    print("="*60)
    print(f"\nLocation: {ASSETS_DIR}")
    print(f"\nTotal files generated: {len(generated_files)}")
    print("\nGenerated files:")
    for f in generated_files:
        print(f"  - {f}")
    print("\nTest Coverage:")
    print("  ✓ Perfect match (PO + Invoice + Delivery Note)")
    print("  ✓ Tax rate mismatch detection")
    print("  ✓ Currency mismatch detection")
    print("  ✓ All documents are 1 page long")
    print("  ✓ Enterprise-prefixed filenames")
    print("  ✓ Realistic company names (no fuzzy matching issues)")


if __name__ == "__main__":
    main()
