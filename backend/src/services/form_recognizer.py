from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from typing import Optional, Dict, Any
import io
import logging

from src.core.config import settings
from src.models.document import DocumentType
from src.services.llm_extractor import LLMExtractor
from src.services.extraction.currency_extractor import CurrencyExtractor
from src.services.extraction.tax_extractor import TaxExtractor

logger = logging.getLogger(__name__)


class FormRecognizerService:
    """Azure Form Recognizer service for document extraction"""

    def __init__(self):
        self.client = DocumentAnalysisClient(
            endpoint=settings.AZURE_FORM_RECOGNIZER_ENDPOINT,
            credential=AzureKeyCredential(settings.AZURE_FORM_RECOGNIZER_KEY),
        )
        self.llm_extractor = LLMExtractor()
        self.currency_extractor = CurrencyExtractor(self.llm_extractor)
        self.tax_extractor = TaxExtractor(self.llm_extractor)

    def analyze_invoice(self, file_content: bytes) -> Dict[str, Any]:
        """Extract data from invoice using pre-built model"""
        try:
            poller = self.client.begin_analyze_document(
                model_id="prebuilt-invoice",
                document=file_content,
            )
            result = poller.result()

            extracted_data = {
                "invoice_number": None,
                "po_number": None,  # PO number from invoice
                "vendor_name": None,
                "vendor_address": None,
                "date": None,
                "total_amount": None,
                "currency_code": None,
                "subtotal": None,
                "tax_amount": None,
                "tax_rate": None,
                "due_date": None,
                "line_items": [],
                "confidence_scores": {},
            }

            # Extract fields from result
            for idx, document in enumerate(result.documents):
                if idx == 0:  # Primary document
                    # Store document fields for later use
                    primary_document_fields = document.fields
                    # Extract invoice number
                    if "InvoiceId" in document.fields:
                        extracted_data["invoice_number"] = document.fields["InvoiceId"].value
                        extracted_data["confidence_scores"]["invoice_number"] = document.fields["InvoiceId"].confidence

                    # Extract PO number (if present on invoice)
                    if "CustomerPurchaseOrder" in document.fields:
                        po_value = document.fields["CustomerPurchaseOrder"].value
                        if po_value:
                            extracted_data["po_number"] = str(po_value)
                            extracted_data["confidence_scores"]["po_number"] = document.fields["CustomerPurchaseOrder"].confidence

                    # Extract vendor name
                    if "VendorName" in document.fields:
                        extracted_data["vendor_name"] = document.fields["VendorName"].value
                        extracted_data["confidence_scores"]["vendor_name"] = document.fields["VendorName"].confidence

                    # Extract vendor address
                    if "VendorAddress" in document.fields:
                        vendor_address = document.fields["VendorAddress"].value
                        if vendor_address:
                            # AddressValue is an object with attributes, not a dict
                            address_parts = []
                            if hasattr(vendor_address, "street_address") and vendor_address.street_address:
                                address_parts.append(
                                    vendor_address.street_address)
                            if hasattr(vendor_address, "city") and vendor_address.city:
                                address_parts.append(vendor_address.city)
                            if hasattr(vendor_address, "state") and vendor_address.state:
                                address_parts.append(vendor_address.state)
                            if hasattr(vendor_address, "postal_code") and vendor_address.postal_code:
                                address_parts.append(
                                    vendor_address.postal_code)
                            extracted_data["vendor_address"] = ", ".join(
                                address_parts) if address_parts else None
                            extracted_data["confidence_scores"]["vendor_address"] = document.fields["VendorAddress"].confidence

                    # Extract invoice date
                    if "InvoiceDate" in document.fields:
                        extracted_data["date"] = document.fields["InvoiceDate"].value
                        extracted_data["confidence_scores"]["date"] = document.fields["InvoiceDate"].confidence

                    # Extract total amount - try multiple fields Azure might use
                    total_amount = None
                    confidence = None

                    # Try AmountDue first (most common)
                    if "AmountDue" in document.fields:
                        amount = document.fields["AmountDue"].value
                        if amount:
                            total_amount = float(amount.amount)
                            confidence = document.fields["AmountDue"].confidence
                    # Fallback to InvoiceTotal
                    elif "InvoiceTotal" in document.fields:
                        amount = document.fields["InvoiceTotal"].value
                        if amount:
                            total_amount = float(amount.amount)
                            confidence = document.fields["InvoiceTotal"].confidence
                    # Fallback to Total
                    elif "Total" in document.fields:
                        amount = document.fields["Total"].value
                        if amount:
                            total_amount = float(amount.amount)
                            confidence = document.fields["Total"].confidence

                    if total_amount is not None:
                        extracted_data["total_amount"] = total_amount
                        if confidence is not None:
                            extracted_data["confidence_scores"]["total_amount"] = confidence

                    # Extract currency using CurrencyExtractor (try before line items for Azure fields)
                    currency_code = self.currency_extractor.extract(
                        azure_result=result,
                        extracted_data=extracted_data,
                        document_fields=document.fields if idx == 0 else None,
                    )
                    if currency_code:
                        extracted_data["currency_code"] = currency_code
                        # Set confidence if available from CurrencyCode field
                        if "CurrencyCode" in document.fields:
                            extracted_data["confidence_scores"]["currency_code"] = document.fields["CurrencyCode"].confidence

                    # Extract subtotal
                    if "SubTotal" in document.fields:
                        subtotal_field = document.fields["SubTotal"].value
                        if subtotal_field:
                            extracted_data["subtotal"] = float(
                                subtotal_field.amount)
                            extracted_data["confidence_scores"]["subtotal"] = document.fields["SubTotal"].confidence

                    # Extract and validate tax using TaxExtractor
                    tax_amount, tax_rate, tax_confidence = self.tax_extractor.extract_and_validate(
                        document_fields=document.fields,
                        extracted_data=extracted_data,
                        azure_result=result,
                    )

                    if tax_amount is not None:
                        extracted_data["tax_amount"] = tax_amount
                        if tax_confidence is not None:
                            extracted_data["confidence_scores"]["tax_amount"] = tax_confidence

                    if tax_rate is not None:
                        extracted_data["tax_rate"] = tax_rate
                        # Final fallback: Calculate tax rate if we have subtotal but no tax_rate yet
                        if not extracted_data.get("tax_rate") and extracted_data.get("subtotal") and extracted_data["subtotal"] > 0 and tax_amount:
                            extracted_data["tax_rate"] = (
                                tax_amount / extracted_data["subtotal"]) * 100

                    # Extract due date
                    if "DueDate" in document.fields:
                        due_date = document.fields["DueDate"].value
                        if due_date:
                            extracted_data["due_date"] = due_date
                            extracted_data["confidence_scores"]["due_date"] = document.fields["DueDate"].confidence

                    # Extract line items
                    if "Items" in document.fields:
                        items = document.fields["Items"].value
                        if items:
                            for item in items:
                                line_item = {
                                    "item_number": None,
                                    "description": None,
                                    "quantity": None,
                                    "unit_price": None,
                                    "line_total": None,
                                }

                                # Handle both dict-like and DocumentField objects
                                item_value = item.value if hasattr(
                                    item, "value") else item

                                # ProductCode/ItemNumber (Azure may extract this)
                                if isinstance(item_value, dict) and "ProductCode" in item_value:
                                    product_code = item_value["ProductCode"]
                                    line_item["item_number"] = product_code.value if hasattr(
                                        product_code, "value") else product_code
                                elif hasattr(item_value, "ProductCode"):
                                    product_code = item_value.ProductCode
                                    line_item["item_number"] = product_code.value if hasattr(
                                        product_code, "value") else product_code

                                # Description
                                if isinstance(item_value, dict) and "Description" in item_value:
                                    desc_field = item_value["Description"]
                                    line_item["description"] = desc_field.value if hasattr(
                                        desc_field, "value") else desc_field
                                elif hasattr(item_value, "Description"):
                                    desc_field = item_value.Description
                                    line_item["description"] = desc_field.value if hasattr(
                                        desc_field, "value") else desc_field

                                # Quantity
                                if isinstance(item_value, dict) and "Quantity" in item_value:
                                    qty_field = item_value["Quantity"]
                                    qty = qty_field.value if hasattr(
                                        qty_field, "value") else qty_field
                                    if qty:
                                        try:
                                            line_item["quantity"] = float(qty)
                                        except (ValueError, TypeError):
                                            pass
                                elif hasattr(item_value, "Quantity"):
                                    qty_field = item_value.Quantity
                                    qty = qty_field.value if hasattr(
                                        qty_field, "value") else qty_field
                                    if qty:
                                        try:
                                            line_item["quantity"] = float(qty)
                                        except (ValueError, TypeError):
                                            pass

                                # Unit Price
                                if isinstance(item_value, dict) and "UnitPrice" in item_value:
                                    price_field = item_value["UnitPrice"]
                                    price = price_field.value if hasattr(
                                        price_field, "value") else price_field
                                    if price:
                                        try:
                                            line_item["unit_price"] = float(price.amount) if hasattr(
                                                price, "amount") else float(price)
                                            # Currency extraction is handled by CurrencyExtractor
                                        except (ValueError, TypeError, AttributeError):
                                            pass
                                elif hasattr(item_value, "UnitPrice"):
                                    price_field = item_value.UnitPrice
                                    price = price_field.value if hasattr(
                                        price_field, "value") else price_field
                                    if price:
                                        try:
                                            line_item["unit_price"] = float(price.amount) if hasattr(
                                                price, "amount") else float(price)
                                            # Currency extraction is handled by CurrencyExtractor
                                        except (ValueError, TypeError, AttributeError):
                                            pass

                                # Amount (line total)
                                if isinstance(item_value, dict) and "Amount" in item_value:
                                    amount_field = item_value["Amount"]
                                    amount = amount_field.value if hasattr(
                                        amount_field, "value") else amount_field
                                    if amount:
                                        try:
                                            line_item["line_total"] = float(amount.amount) if hasattr(
                                                amount, "amount") else float(amount)
                                            # Currency extraction is handled by CurrencyExtractor
                                        except (ValueError, TypeError, AttributeError):
                                            pass
                                elif hasattr(item_value, "Amount"):
                                    amount_field = item_value.Amount
                                    amount = amount_field.value if hasattr(
                                        amount_field, "value") else amount_field
                                    if amount:
                                        try:
                                            line_item["line_total"] = float(amount.amount) if hasattr(
                                                amount, "amount") else float(amount)
                                            # Currency extraction is handled by CurrencyExtractor
                                        except (ValueError, TypeError, AttributeError):
                                            pass

                                extracted_data["line_items"].append(line_item)

                    # Try currency extraction again after line items (for symbol inference fallback)
                    if not extracted_data.get("currency_code"):
                        currency_code = self.currency_extractor.extract(
                            azure_result=result,
                            extracted_data=extracted_data,
                            document_fields=primary_document_fields,
                        )
                        if currency_code:
                            extracted_data["currency_code"] = currency_code

            return extracted_data

        except Exception as e:
            raise Exception(f"Failed to analyze invoice: {str(e)}")

    def analyze_purchase_order(self, file_content: bytes) -> Dict[str, Any]:
        """Extract data from purchase order using pre-built model"""
        try:
            # Use general document model for PO (no pre-built PO model)
            poller = self.client.begin_analyze_document(
                model_id="prebuilt-layout",
                document=file_content,
            )
            result = poller.result()

            extracted_data = {
                "po_number": None,
                "vendor_name": None,
                "vendor_address": None,
                "date": None,
                "total_amount": None,
                "currency_code": None,
                "subtotal": None,
                "tax_amount": None,
                "tax_rate": None,
                "line_items": [],
                "confidence_scores": {},
            }

            # Extract from paragraphs (more reliable than key-value pairs for layout model)
            if hasattr(result, "paragraphs"):
                paragraphs = result.paragraphs
                for i, para in enumerate(paragraphs):
                    content = para.content.strip()
                    content_lower = content.lower()

                    # Extract PO number
                    if not extracted_data["po_number"]:
                        if "po number:" in content_lower or "purchase order:" in content_lower:
                            # Next paragraph should be the PO number
                            if i + 1 < len(paragraphs):
                                next_para = paragraphs[i + 1].content.strip()
                                if next_para and not next_para.endswith(":"):
                                    extracted_data["po_number"] = next_para

                    # Extract vendor name
                    if not extracted_data["vendor_name"]:
                        if "vendor:" in content_lower:
                            # Next paragraph should be the vendor name
                            if i + 1 < len(paragraphs):
                                next_para = paragraphs[i + 1].content.strip()
                                if next_para and not next_para.endswith(":"):
                                    extracted_data["vendor_name"] = next_para

                    # Extract vendor address (multi-line)
                    if not extracted_data["vendor_address"] and extracted_data["vendor_name"]:
                        # Look for address after vendor name
                        vendor_idx = None
                        for j, p in enumerate(paragraphs):
                            if p.content.strip() == extracted_data["vendor_name"]:
                                vendor_idx = j
                                break
                        if vendor_idx and vendor_idx + 1 < len(paragraphs):
                            address_parts = []
                            for j in range(vendor_idx + 1, min(vendor_idx + 5, len(paragraphs))):
                                addr_line = paragraphs[j].content.strip()
                                if addr_line and not addr_line.endswith(":") and len(addr_line) > 2:
                                    address_parts.append(addr_line)
                                else:
                                    break
                            if address_parts:
                                extracted_data["vendor_address"] = ", ".join(
                                    address_parts)

            # Extract from tables (line items)
            if hasattr(result, "tables"):
                for table in result.tables:
                    # Skip header row (row_index 0)
                    for row_idx in range(1, table.row_count):
                        row_cells = [
                            cell for cell in table.cells if cell.row_index == row_idx]
                        if len(row_cells) >= 3:  # At least item #, description, qty
                            # Sort by column index
                            row_cells.sort(key=lambda x: x.column_index)

                            line_item = {
                                "item_number": row_cells[0].content.strip() if len(row_cells) > 0 else None,
                                "description": row_cells[1].content.strip() if len(row_cells) > 1 else None,
                                "quantity": None,
                                "unit_price": None,
                                "line_total": None,
                            }

                            # Try to parse quantities and prices
                            if len(row_cells) > 2:
                                try:
                                    qty_str = row_cells[2].content.strip()
                                    line_item["quantity"] = float(qty_str)
                                except (ValueError, IndexError):
                                    pass

                            if len(row_cells) > 3:
                                try:
                                    # Remove all currency symbols and formatting
                                    price_str = row_cells[3].content
                                    # Remove common currency symbols
                                    for symbol in ["$", "€", "£", "¥", "C$", "A$", "USD", "EUR", "GBP", "JPY", "CAD", "AUD"]:
                                        price_str = price_str.replace(
                                            symbol, "")
                                    # Remove commas and whitespace
                                    price_str = price_str.replace(
                                        ",", "").strip()
                                    if price_str:
                                        line_item["unit_price"] = float(
                                            price_str)
                                except (ValueError, IndexError, AttributeError):
                                    pass

                            if len(row_cells) > 4:
                                try:
                                    # Remove all currency symbols and formatting
                                    total_str = row_cells[4].content
                                    # Remove common currency symbols
                                    for symbol in ["$", "€", "£", "¥", "C$", "A$", "USD", "EUR", "GBP", "JPY", "CAD", "AUD"]:
                                        total_str = total_str.replace(
                                            symbol, "")
                                    # Remove commas and whitespace
                                    total_str = total_str.replace(
                                        ",", "").strip()
                                    if total_str:
                                        line_item["line_total"] = float(
                                            total_str)
                                except (ValueError, IndexError, AttributeError):
                                    pass

                            extracted_data["line_items"].append(line_item)

            # ============================================================
            # PHASE 1: GROUND TRUTH - Calculate subtotal from line items
            # ============================================================
            # This is ALWAYS reliable - line items are from structured tables
            calculated_subtotal = None
            if extracted_data["line_items"]:
                try:
                    calculated_subtotal = sum(
                        float(item.get("line_total", 0) or 0)
                        for item in extracted_data["line_items"]
                    )
                    if calculated_subtotal > 0:
                        # Use calculated as ground truth
                        extracted_data["subtotal"] = calculated_subtotal
                except (ValueError, TypeError):
                    pass

            # ============================================================
            # PHASE 2: Extract from tables (structured, reliable)
            # ============================================================
            # Extract subtotal and total from tables (currency and tax handled by extractors)
            if hasattr(result, "tables"):
                import re
                for table in result.tables:
                    for row_idx in range(table.row_count):
                        row_cells = [
                            cell for cell in table.cells if cell.row_index == row_idx]
                        if len(row_cells) >= 2:
                            row_cells.sort(key=lambda x: x.column_index)
                            label = row_cells[0].content.strip().lower()
                            value_str = row_cells[1].content.strip() if len(
                                row_cells) > 1 else ""

                            # Extract subtotal from table
                            if not extracted_data["subtotal"] and "subtotal" in label:
                                try:
                                    # Remove currency symbols (extractors handle currency)
                                    for symbol in ["$", "€", "£", "¥", "C$", "A$", "USD", "EUR", "GBP", "JPY", "CAD", "AUD"]:
                                        value_str = value_str.replace(
                                            symbol, "")
                                    value_str = value_str.replace(
                                        ",", "").strip()
                                    if value_str:
                                        table_subtotal = float(value_str)
                                        # Validate against calculated (if available)
                                        if calculated_subtotal:
                                            # 1% tolerance
                                            if abs(table_subtotal - calculated_subtotal) / calculated_subtotal < 0.01:
                                                extracted_data["subtotal"] = table_subtotal
                                        else:
                                            extracted_data["subtotal"] = table_subtotal
                                except (ValueError, IndexError):
                                    pass

                            # Extract total from table
                            if not extracted_data["total_amount"] and "total" in label and "subtotal" not in label:
                                try:
                                    # Remove currency symbols (extractors handle currency)
                                    for symbol in ["$", "€", "£", "¥", "C$", "A$", "USD", "EUR", "GBP", "JPY", "CAD", "AUD"]:
                                        value_str = value_str.replace(
                                            symbol, "")
                                    value_str = value_str.replace(
                                        ",", "").strip()
                                    if value_str:
                                        extracted_data["total_amount"] = float(
                                            value_str)
                                except (ValueError, IndexError):
                                    pass

            # ============================================================
            # PHASE 3: LLM-Enhanced Extraction from Paragraphs
            # ============================================================
            # Use LLM for complex cases where paragraphs are combined
            if hasattr(result, "paragraphs"):
                import re
                paragraphs = result.paragraphs
                paragraph_texts = [para.content.strip() for para in paragraphs]

                # Try LLM extraction for totals section
                if self.llm_extractor.enabled:
                    llm_totals = self.llm_extractor.extract_totals_section(
                        paragraph_texts)
                    if llm_totals and llm_totals.confidence > 0.7:
                        # Use LLM extraction if confidence is high
                        if not extracted_data["subtotal"] and llm_totals.subtotal:
                            # Validate LLM subtotal against calculated
                            if calculated_subtotal:
                                if abs(llm_totals.subtotal - calculated_subtotal) / calculated_subtotal < 0.01:
                                    extracted_data["subtotal"] = llm_totals.subtotal
                            else:
                                extracted_data["subtotal"] = llm_totals.subtotal

                        if not extracted_data.get("tax_rate") and llm_totals.tax_rate:
                            extracted_data["tax_rate"] = llm_totals.tax_rate

                        if not extracted_data.get("tax_amount") and llm_totals.tax_amount:
                            extracted_data["tax_amount"] = llm_totals.tax_amount

                        if not extracted_data["total_amount"] and llm_totals.total_amount:
                            extracted_data["total_amount"] = llm_totals.total_amount

                # Fallback to regex extraction if LLM not available or low confidence
                for i, para in enumerate(paragraphs):
                    content = para.content.strip()
                    content_lower = content.lower()

                    # Currency extraction is handled by CurrencyExtractor (called after line items)

                    # Extract subtotal (regex fallback)
                    if not extracted_data["subtotal"]:
                        if "subtotal:" in content_lower:
                            numbers = re.findall(r'[\d,]+\.?\d*', content)
                            if numbers:
                                try:
                                    num_str = numbers[-1].replace(",", "").replace("$", "").replace(
                                        "€", "").replace("£", "").replace("¥", "").strip()
                                    regex_subtotal = float(num_str)
                                    # Validate against calculated
                                    if calculated_subtotal:
                                        if abs(regex_subtotal - calculated_subtotal) / calculated_subtotal < 0.01:
                                            extracted_data["subtotal"] = regex_subtotal
                                    else:
                                        extracted_data["subtotal"] = regex_subtotal
                                except (ValueError, IndexError):
                                    pass

                    # Tax extraction is handled by TaxExtractor (called after line items)

                    # Extract total (regex fallback)
                    if not extracted_data["total_amount"]:
                        if "total:" in content_lower and "subtotal" not in content_lower:
                            numbers = re.findall(r'[\d,]+\.?\d*', content)
                            if numbers:
                                try:
                                    num_str = numbers[-1].replace(",", "").replace("$", "").replace(
                                        "€", "").replace("£", "").replace("¥", "").strip()
                                    extracted_data["total_amount"] = float(
                                        num_str)
                                except (ValueError, IndexError):
                                    pass

            # ============================================================
            # PHASE 4: Ensure subtotal is set (use calculated as ground truth)
            # ============================================================
            if not extracted_data["subtotal"] and calculated_subtotal:
                extracted_data["subtotal"] = calculated_subtotal

            # ============================================================
            # PHASE 4: Extract currency and tax using extractors
            # ============================================================
            # Extract currency using CurrencyExtractor (after line items for symbol inference)
            currency_code = self.currency_extractor.extract(
                azure_result=result,
                extracted_data=extracted_data,
                document_fields=None,  # PO doesn't have Azure document fields
            )
            if currency_code:
                extracted_data["currency_code"] = currency_code

            # Extract and validate tax using TaxExtractor
            # For PO, tax_amount may already be extracted from LLM totals section
            # TaxExtractor will validate and correct if needed
            tax_amount, tax_rate, tax_confidence = self.tax_extractor.extract_and_validate(
                document_fields={},  # PO doesn't have Azure fields
                extracted_data=extracted_data,
                azure_result=result,
            )

            if tax_amount is not None:
                extracted_data["tax_amount"] = tax_amount
            if tax_rate is not None:
                extracted_data["tax_rate"] = tax_rate

            # Calculate tax_amount from subtotal × tax_rate if we have both
            subtotal = extracted_data.get("subtotal")
            if subtotal and tax_rate and not extracted_data.get("tax_amount"):
                extracted_data["tax_amount"] = subtotal * (tax_rate / 100)

            # Calculate tax_rate from tax_amount if missing
            if subtotal and extracted_data.get("tax_amount") and not tax_rate:
                try:
                    tax_amount = float(extracted_data["tax_amount"])
                    if subtotal > 0:
                        extracted_data["tax_rate"] = (
                            tax_amount / subtotal) * 100
                except (ValueError, TypeError, ZeroDivisionError):
                    pass

            return extracted_data

        except Exception as e:
            raise Exception(f"Failed to analyze purchase order: {str(e)}")

    def analyze_delivery_note(self, file_content: bytes) -> Dict[str, Any]:
        """Extract data from delivery note using general layout model"""
        try:
            poller = self.client.begin_analyze_document(
                model_id="prebuilt-layout",
                document=file_content,
            )
            result = poller.result()

            extracted_data = {
                "delivery_note_number": None,
                "po_number": None,
                "vendor_name": None,
                "vendor_address": None,
                "date": None,
                "line_items": [],
                "confidence_scores": {},
            }

            # Extract from paragraphs (more reliable than key-value pairs for layout model)
            if hasattr(result, "paragraphs"):
                paragraphs = result.paragraphs
                for i, para in enumerate(paragraphs):
                    content = para.content.strip()
                    content_lower = content.lower()

                    # Extract delivery note number
                    if not extracted_data["delivery_note_number"]:
                        if "delivery note" in content_lower or "dn" in content_lower:
                            # Next paragraph should be the DN number
                            if i + 1 < len(paragraphs):
                                next_para = paragraphs[i + 1].content.strip()
                                if next_para and not next_para.endswith(":") and ("DN-" in next_para or "dn-" in next_para.lower()):
                                    extracted_data["delivery_note_number"] = next_para

                    # Extract PO number
                    if not extracted_data["po_number"]:
                        if "po number:" in content_lower:
                            # Next paragraph should be the PO number
                            if i + 1 < len(paragraphs):
                                next_para = paragraphs[i + 1].content.strip()
                                if next_para and not next_para.endswith(":"):
                                    extracted_data["po_number"] = next_para

                    # Extract vendor name
                    if not extracted_data["vendor_name"]:
                        if "from:" in content_lower:
                            # Next paragraph should be the vendor name
                            if i + 1 < len(paragraphs):
                                next_para = paragraphs[i + 1].content.strip()
                                if next_para and not next_para.endswith(":"):
                                    extracted_data["vendor_name"] = next_para

            # Extract line items from tables
            if hasattr(result, "tables"):
                for table in result.tables:
                    # Skip header row (row_index 0)
                    for row_idx in range(1, table.row_count):
                        row_cells = [
                            cell for cell in table.cells if cell.row_index == row_idx]
                        if len(row_cells) >= 2:  # At least item # and description
                            # Sort by column index
                            row_cells.sort(key=lambda x: x.column_index)

                            line_item = {
                                "item_number": row_cells[0].content.strip() if len(row_cells) > 0 else None,
                                "description": row_cells[1].content.strip() if len(row_cells) > 1 else None,
                                "quantity": None,
                            }

                            # Try to find quantity (could be in different columns)
                            for cell in row_cells[2:]:
                                try:
                                    qty = float(cell.content.strip())
                                    line_item["quantity"] = qty
                                    break
                                except (ValueError, TypeError):
                                    pass

                            extracted_data["line_items"].append(line_item)

            return extracted_data

        except Exception as e:
            raise Exception(f"Failed to analyze delivery note: {str(e)}")

    def extract_document(self, document_type: DocumentType, file_content: bytes) -> Dict[str, Any]:
        """Extract data based on document type"""
        if document_type == DocumentType.INVOICE:
            return self.analyze_invoice(file_content)
        elif document_type == DocumentType.PURCHASE_ORDER:
            return self.analyze_purchase_order(file_content)
        elif document_type == DocumentType.DELIVERY_NOTE:
            return self.analyze_delivery_note(file_content)
        else:
            raise ValueError(f"Unsupported document type: {document_type}")


form_recognizer_service = FormRecognizerService()
