from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from typing import Optional, Dict, Any
import io
import logging

from src.core.config import settings
from src.models.document import DocumentType
from src.services.llm_extractor import LLMExtractor

logger = logging.getLogger(__name__)


class FormRecognizerService:
    """Azure Form Recognizer service for document extraction"""

    def __init__(self):
        self.client = DocumentAnalysisClient(
            endpoint=settings.AZURE_FORM_RECOGNIZER_ENDPOINT,
            credential=AzureKeyCredential(settings.AZURE_FORM_RECOGNIZER_KEY),
        )
        self.llm_extractor = LLMExtractor()

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

                    # Extract currency code - try multiple methods
                    currency_extracted = False

                    # Extract total amount - try multiple fields Azure might use
                    total_amount = None
                    confidence = None

                    # Try AmountDue first (most common)
                    if "AmountDue" in document.fields:
                        amount = document.fields["AmountDue"].value
                        if amount:
                            total_amount = float(amount.amount)
                            confidence = document.fields["AmountDue"].confidence
                            # Extract currency from CurrencyValue if available
                            if hasattr(amount, "currency_code") and amount.currency_code:
                                extracted_data["currency_code"] = str(
                                    amount.currency_code).upper()
                                currency_extracted = True
                                logger.info(
                                    f"[INVOICE CURRENCY] Extracted from AmountDue CurrencyValue: {extracted_data['currency_code']}")
                    # Fallback to InvoiceTotal
                    elif "InvoiceTotal" in document.fields:
                        amount = document.fields["InvoiceTotal"].value
                        if amount:
                            total_amount = float(amount.amount)
                            confidence = document.fields["InvoiceTotal"].confidence
                            # Extract currency from CurrencyValue if available
                            if hasattr(amount, "currency_code") and amount.currency_code:
                                extracted_data["currency_code"] = str(
                                    amount.currency_code).upper()
                                currency_extracted = True
                                logger.info(
                                    f"[INVOICE CURRENCY] Extracted from InvoiceTotal CurrencyValue: {extracted_data['currency_code']}")
                    # Fallback to Total
                    elif "Total" in document.fields:
                        amount = document.fields["Total"].value
                        if amount:
                            total_amount = float(amount.amount)
                            confidence = document.fields["Total"].confidence
                            # Extract currency from CurrencyValue if available
                            if hasattr(amount, "currency_code") and amount.currency_code:
                                extracted_data["currency_code"] = str(
                                    amount.currency_code).upper()
                                currency_extracted = True
                                logger.info(
                                    f"[INVOICE CURRENCY] Extracted from Total CurrencyValue: {extracted_data['currency_code']}")

                    if total_amount is not None:
                        extracted_data["total_amount"] = total_amount
                        if confidence is not None:
                            extracted_data["confidence_scores"]["total_amount"] = confidence

                    # Try CurrencyCode field (this should be checked BEFORE line items)
                    if not currency_extracted and "CurrencyCode" in document.fields:
                        currency = document.fields["CurrencyCode"].value
                        if currency:
                            extracted_data["currency_code"] = str(currency)
                            extracted_data["confidence_scores"]["currency_code"] = document.fields["CurrencyCode"].confidence
                            currency_extracted = True
                            logger.info(
                                f"[INVOICE CURRENCY] Extracted from Azure CurrencyCode field: {extracted_data['currency_code']}")

                    # Fallback: Extract from document content - try multiple sources
                    if not currency_extracted:
                        import re
                        logger.info(
                            "[INVOICE CURRENCY] Trying fallback methods: checking document content")

                        # Collect all text content from various sources
                        all_text_content = []

                        # Method 1: Try paragraphs (if available)
                        if hasattr(result, "paragraphs") and result.paragraphs:
                            all_text_content.extend(
                                [para.content for para in result.paragraphs])
                            logger.info(
                                f"[INVOICE CURRENCY] Found {len(result.paragraphs)} paragraphs")

                        # Method 2: Try pages (alternative structure)
                        if not all_text_content and hasattr(result, "pages") and result.pages:
                            for page in result.pages:
                                if hasattr(page, "paragraphs"):
                                    all_text_content.extend(
                                        [para.content for para in page.paragraphs])
                            logger.info(
                                f"[INVOICE CURRENCY] Found {len(all_text_content)} paragraphs from pages")

                        # Method 3: Extract text from document fields (vendor name, invoice number, etc.)
                        if hasattr(result, "documents") and result.documents:
                            for doc in result.documents:
                                # Get all field values as strings
                                if hasattr(doc, "fields"):
                                    for field_name, field_value in doc.fields.items():
                                        if field_value and hasattr(field_value, "value"):
                                            field_str = str(field_value.value)
                                            if field_str:
                                                all_text_content.append(
                                                    field_str)

                        # Method 4: Check line item descriptions and unit prices (they often contain currency info)
                        for item in extracted_data.get("line_items", []):
                            desc = str(item.get("description", ""))
                            if desc:
                                all_text_content.append(desc)
                            # Unit prices might have currency symbols
                            unit_price = item.get("unit_price")
                            if unit_price:
                                all_text_content.append(str(unit_price))

                        # Method 5: Check extracted fields we already have
                        if extracted_data.get("vendor_name"):
                            all_text_content.append(
                                str(extracted_data["vendor_name"]))
                        if extracted_data.get("invoice_number"):
                            all_text_content.append(
                                str(extracted_data["invoice_number"]))
                        if extracted_data.get("total_amount"):
                            all_text_content.append(
                                str(extracted_data["total_amount"]))

                        logger.info(
                            f"[INVOICE CURRENCY] Collected {len(all_text_content)} text segments from various sources")

                        # Check all collected content
                        for content in all_text_content:
                            if not content:
                                continue
                            content_str = str(content).strip()
                            content_upper = content_str.upper()

                            # Method 1: Look for currency codes
                            if any(code in content_upper for code in ["USD", "EUR", "GBP", "JPY", "CAD", "AUD"]):
                                currency_match = re.search(
                                    r'\b(USD|EUR|GBP|JPY|CAD|AUD)\b', content_str, re.IGNORECASE)
                                if currency_match:
                                    extracted_data["currency_code"] = currency_match.group(
                                        1).upper()
                                    currency_extracted = True
                                    logger.info(
                                        f"[INVOICE CURRENCY] Extracted from document text (code): {extracted_data['currency_code']}")
                                    break

                            # Method 2: Infer from currency symbols (improved EUR detection)
                            if not currency_extracted:
                                # Check for EUR first (before USD) to avoid false positives
                                # EUR can be represented as € or EUR or Euro
                                if "€" in content_str or "EUR" in content_upper or "EURO" in content_upper:
                                    extracted_data["currency_code"] = "EUR"
                                    currency_extracted = True
                                    logger.info(
                                        f"[INVOICE CURRENCY] Inferred from symbol/text (€/EUR): EUR")
                                    break
                                elif "£" in content_str or "GBP" in content_upper:
                                    extracted_data["currency_code"] = "GBP"
                                    currency_extracted = True
                                    logger.info(
                                        f"[INVOICE CURRENCY] Inferred from symbol/text (£/GBP): GBP")
                                    break
                                elif "$" in content_str and "C$" not in content_str and "A$" not in content_str:
                                    # Only infer USD if no other currency symbols present
                                    extracted_data["currency_code"] = "USD"
                                    currency_extracted = True
                                    logger.info(
                                        f"[INVOICE CURRENCY] Inferred from symbol ($): USD")
                                    break
                                elif "C$" in content_str:
                                    extracted_data["currency_code"] = "CAD"
                                    currency_extracted = True
                                    logger.info(
                                        f"[INVOICE CURRENCY] Inferred from symbol (C$): CAD")
                                    break
                                elif "A$" in content_str:
                                    extracted_data["currency_code"] = "AUD"
                                    currency_extracted = True
                                    logger.info(
                                        f"[INVOICE CURRENCY] Inferred from symbol (A$): AUD")
                                    break

                        # STEP 4: Use LLM to extract currency if still not found
                        if not currency_extracted and self.llm_extractor.enabled:
                            # Get all document text for LLM extraction from multiple sources
                            llm_doc_text = ""

                            # Try paragraphs first
                            if hasattr(result, "paragraphs") and result.paragraphs:
                                llm_doc_text = "\n".join(
                                    [para.content for para in result.paragraphs[:20]])

                            # If no paragraphs, use the collected text content
                            if not llm_doc_text and all_text_content:
                                # First 50 text segments
                                llm_doc_text = "\n".join(all_text_content[:50])

                            # Also try to get text from document fields
                            if not llm_doc_text and hasattr(result, "documents") and result.documents:
                                field_texts = []
                                for doc in result.documents:
                                    if hasattr(doc, "fields"):
                                        for field_name, field_value in doc.fields.items():
                                            if field_value:
                                                try:
                                                    if hasattr(field_value, "value"):
                                                        field_texts.append(
                                                            f"{field_name}: {field_value.value}")
                                                except:
                                                    pass
                                if field_texts:
                                    llm_doc_text = "\n".join(field_texts)

                            if llm_doc_text:
                                logger.info(
                                    f"[INVOICE CURRENCY] Using LLM extraction with {len(llm_doc_text)} characters of text")
                                # Use TRUE LLM extraction (not just regex)
                                llm_currency = self.llm_extractor.extract_currency(
                                    llm_doc_text)
                                if llm_currency and llm_currency.currency_code and llm_currency.confidence > 0.7:
                                    extracted_data["currency_code"] = llm_currency.currency_code.upper(
                                    )
                                    currency_extracted = True
                                    logger.info(
                                        f"[INVOICE CURRENCY] LLM extracted currency: {extracted_data['currency_code']} "
                                        f"(confidence: {llm_currency.confidence:.2f}, reasoning: {llm_currency.reasoning[:50]})"
                                    )
                                else:
                                    # Fallback to regex if LLM extraction fails or low confidence
                                    import re
                                    currency_patterns = [
                                        r'\b(USD|EUR|GBP|JPY|CAD|AUD)\b',
                                        r'Currency[:\s]+([A-Z]{3})',
                                        r'([A-Z]{3})\s+Currency',
                                    ]
                                    for pattern in currency_patterns:
                                        match = re.search(
                                            pattern, llm_doc_text, re.IGNORECASE)
                                        if match:
                                            currency_code = match.group(
                                                1).upper()
                                            if currency_code in ["USD", "EUR", "GBP", "JPY", "CAD", "AUD"]:
                                                extracted_data["currency_code"] = currency_code
                                                currency_extracted = True
                                                logger.info(
                                                    f"[INVOICE CURRENCY] Extracted via regex fallback: {currency_code}")
                                                break

                        # Final fallback: Infer from price formats in line items
                        if not currency_extracted:
                            # Check unit prices and line totals for currency symbols
                            for item in extracted_data.get("line_items", []):
                                unit_price = item.get("unit_price")
                                line_total = item.get("line_total")

                                # Check if prices are formatted as strings with currency symbols
                                price_str = ""
                                if unit_price:
                                    price_str = str(unit_price)
                                elif line_total:
                                    price_str = str(line_total)

                                if price_str:
                                    if "€" in price_str or "EUR" in price_str.upper():
                                        extracted_data["currency_code"] = "EUR"
                                        currency_extracted = True
                                        logger.info(
                                            "[INVOICE CURRENCY] Inferred from price format: EUR")
                                        break
                                    elif "£" in price_str or "GBP" in price_str.upper():
                                        extracted_data["currency_code"] = "GBP"
                                        currency_extracted = True
                                        logger.info(
                                            "[INVOICE CURRENCY] Inferred from price format: GBP")
                                        break
                                    elif "$" in price_str and "C$" not in price_str and "A$" not in price_str:
                                        extracted_data["currency_code"] = "USD"
                                        currency_extracted = True
                                        logger.info(
                                            "[INVOICE CURRENCY] Inferred from price format: USD")
                                        break

                        if not currency_extracted:
                            logger.warning(
                                f"[INVOICE CURRENCY] No currency found in {len(all_text_content)} text segments - currency extraction failed")
                            # Log LLM status for debugging
                            if not self.llm_extractor.enabled:
                                logger.warning(
                                    "[INVOICE CURRENCY] LLM extractor is DISABLED - currency extraction may be incomplete!")
                                logger.warning(
                                    "[INVOICE CURRENCY] To enable: set OPENAI_API_KEY in environment variables")
                            else:
                                logger.warning(
                                    "[INVOICE CURRENCY] LLM extractor is enabled but no text content available for extraction")

                    # Extract subtotal
                    if "SubTotal" in document.fields:
                        subtotal_field = document.fields["SubTotal"].value
                        if subtotal_field:
                            extracted_data["subtotal"] = float(
                                subtotal_field.amount)
                            extracted_data["confidence_scores"]["subtotal"] = document.fields["SubTotal"].confidence

                    # Extract tax amount - try multiple fields with validation
                    tax_amount = None
                    tax_confidence = None
                    tax_field_used = None

                    # Try "Tax" field first (most specific)
                    if "Tax" in document.fields:
                        tax_field = document.fields["Tax"].value
                        if tax_field:
                            try:
                                tax_amount = float(tax_field.amount)
                                tax_confidence = document.fields["Tax"].confidence
                                tax_field_used = "Tax"
                                logger.info(
                                    f"[INVOICE TAX] Extracted from 'Tax' field: ${tax_amount:.2f} (confidence: {tax_confidence:.2f})")
                            except (ValueError, TypeError, AttributeError) as e:
                                logger.warning(
                                    f"[INVOICE TAX] Failed to extract from 'Tax' field: {e}")

                    # Fallback to "TotalTax" field
                    if tax_amount is None and "TotalTax" in document.fields:
                        tax_field = document.fields["TotalTax"].value
                        if tax_field:
                            try:
                                tax_amount = float(tax_field.amount)
                                tax_confidence = document.fields["TotalTax"].confidence
                                tax_field_used = "TotalTax"
                                logger.info(
                                    f"[INVOICE TAX] Extracted from 'TotalTax' field: ${tax_amount:.2f} (confidence: {tax_confidence:.2f})")
                            except (ValueError, TypeError, AttributeError) as e:
                                logger.warning(
                                    f"[INVOICE TAX] Failed to extract from 'TotalTax' field: {e}")

                    # Validate tax_amount is reasonable (not the total amount)
                    if tax_amount is not None and extracted_data.get("total_amount"):
                        total = float(extracted_data["total_amount"])
                        # Tax should be less than total (usually 0-30% of total)
                        if tax_amount >= total:
                            logger.warning(
                                f"[INVOICE TAX] VALIDATION FAILED: tax_amount (${tax_amount:.2f}) >= total_amount (${total:.2f}). "
                                f"This is likely an extraction error - extracted 'Total' instead of 'Tax'"
                            )
                            # Don't use this value - it's clearly wrong
                            tax_amount = None
                            tax_confidence = None
                            tax_field_used = None
                        elif tax_amount > total * 0.5:
                            logger.warning(
                                f"[INVOICE TAX] VALIDATION WARNING: tax_amount (${tax_amount:.2f}) is >50% of total (${total:.2f}). "
                                f"This is unusually high - may be extraction error"
                            )

                    # ============================================================
                    # LLM VALIDATION: Validate invoice tax extraction (AGGRESSIVE)
                    # ============================================================
                    # This ensures robustness - LLM validates if extracted tax
                    # matches calculated tax from subtotal × tax_rate
                    # We're more aggressive here because invoice extraction can be unreliable

                    # Log LLM status for debugging
                    if not self.llm_extractor.enabled:
                        logger.warning(
                            "[INVOICE TAX] LLM extractor is DISABLED - tax extraction fixes will not work!")
                        logger.warning(
                            "[INVOICE TAX] To enable: set OPENAI_API_KEY in environment variables")

                    if tax_amount is not None and extracted_data["subtotal"] and extracted_data["subtotal"] > 0:
                        # Calculate tax_rate from tax_amount and subtotal (GROUND TRUTH)
                        calculated_tax_rate_from_amount = (
                            tax_amount / extracted_data["subtotal"]) * 100

                        # Get Azure's tax_rate if available (may be wrong)
                        azure_tax_rate = None
                        if "TaxRate" in document.fields:
                            try:
                                tax_rate_field = document.fields["TaxRate"].value
                                if tax_rate_field:
                                    # Azure might return as percentage string or number
                                    if isinstance(tax_rate_field, str):
                                        azure_tax_rate = float(
                                            tax_rate_field.replace("%", ""))
                                    else:
                                        # Convert decimal to percentage
                                        azure_tax_rate = float(
                                            tax_rate_field) * 100
                            except (ValueError, TypeError, AttributeError):
                                pass

                        # STEP 1: Use LLM to extract tax_rate from document text FIRST (most reliable)
                        llm_tax_rate = None
                        if self.llm_extractor.enabled:
                            # Get all relevant text for tax extraction
                            doc_text = ""
                            if hasattr(result, "paragraphs"):
                                doc_text = "\n".join([
                                    para.content for para in result.paragraphs
                                    if any(keyword in para.content.lower() for keyword in ["tax", "vat", "total", "subtotal", "%"])
                                ])

                            if doc_text:
                                llm_tax = self.llm_extractor.extract_tax_rate(
                                    doc_text)
                                if llm_tax and llm_tax.tax_rate and llm_tax.confidence > 0.7:
                                    llm_tax_rate = llm_tax.tax_rate
                                    logger.info(
                                        f"[INVOICE TAX] LLM extracted tax_rate: {llm_tax_rate}% (confidence: {llm_tax.confidence:.2f})"
                                    )

                        # STEP 2: Determine which tax_rate to use (priority: LLM > Calculated from amount > Azure)
                        final_tax_rate = None
                        if llm_tax_rate:
                            # LLM is most reliable - use it
                            final_tax_rate = llm_tax_rate
                            logger.info(
                                f"[INVOICE TAX] Using LLM tax_rate: {final_tax_rate}%")
                        elif calculated_tax_rate_from_amount:
                            # Use calculated from amount (ground truth)
                            final_tax_rate = calculated_tax_rate_from_amount
                            logger.info(
                                f"[INVOICE TAX] Using calculated tax_rate from amount: {final_tax_rate}%")
                        elif azure_tax_rate:
                            # Fallback to Azure (may be wrong)
                            final_tax_rate = azure_tax_rate
                            logger.warning(
                                f"[INVOICE TAX] Using Azure tax_rate (may be unreliable): {final_tax_rate}%")

                        # STEP 3: Validate and correct tax_amount using the chosen tax_rate
                        if final_tax_rate:
                            expected_tax_amount = extracted_data["subtotal"] * (
                                final_tax_rate / 100)
                            difference = abs(tax_amount - expected_tax_amount)
                            # 1% tolerance
                            tolerance = extracted_data["subtotal"] * 0.01

                            # If we have Azure tax_rate, check if it matches our chosen rate
                            if azure_tax_rate and abs(azure_tax_rate - final_tax_rate) > 0.5:
                                logger.warning(
                                    f"[INVOICE TAX] Azure tax_rate ({azure_tax_rate}%) differs from chosen rate ({final_tax_rate}%) - Azure may be wrong"
                                )

                            # Always use LLM validation if available
                            if self.llm_extractor.enabled:
                                # Get document text for validation context
                                doc_text = ""
                                if hasattr(result, "paragraphs"):
                                    doc_text = "\n".join([
                                        para.content for para in result.paragraphs
                                        if "tax" in para.content.lower() or "total" in para.content.lower() or "subtotal" in para.content.lower()
                                    ])

                                validation = self.llm_extractor.validate_tax_discrepancy(
                                    extracted_tax_amount=tax_amount,
                                    calculated_tax_amount=expected_tax_amount,
                                    subtotal=extracted_data["subtotal"],
                                    tax_rate=final_tax_rate,
                                    document_context=doc_text
                                )

                                if validation and validation.confidence > 0.7:
                                    logger.info(
                                        f"[INVOICE TAX VALIDATION] LLM result: is_extraction_error={validation.is_extraction_error}, "
                                        f"confidence={validation.confidence:.2f}, reasoning={validation.reasoning[:100]}"
                                    )
                                    if validation.is_extraction_error:
                                        # Use calculated (more reliable)
                                        logger.info(
                                            f"[INVOICE TAX VALIDATION] CORRECTING: Using calculated tax_amount={expected_tax_amount:.2f} "
                                            f"instead of extracted={tax_amount:.2f}"
                                        )
                                        tax_amount = expected_tax_amount
                                        extracted_data["tax_rate"] = final_tax_rate
                                    else:
                                        # Real discrepancy - use extracted but keep calculated rate
                                        logger.info(
                                            f"[INVOICE TAX VALIDATION] Real discrepancy detected, keeping extracted tax_amount={tax_amount:.2f}"
                                        )
                                        extracted_data["tax_rate"] = final_tax_rate
                                elif difference > tolerance:
                                    # LLM validation failed but difference is significant - use calculated
                                    logger.warning(
                                        f"[INVOICE TAX VALIDATION] LLM validation failed, but difference={difference:.2f} > tolerance={tolerance:.2f}, using calculated"
                                    )
                                    tax_amount = expected_tax_amount
                                    extracted_data["tax_rate"] = final_tax_rate
                                else:
                                    # Difference is small - use extracted
                                    extracted_data["tax_rate"] = final_tax_rate
                            else:
                                # No LLM - use simple validation
                                logger.info(
                                    f"[INVOICE TAX VALIDATION] LLM not enabled, using simple validation. "
                                    f"Difference={difference:.2f}, Tolerance={tolerance:.2f}"
                                )
                                if difference > tolerance:
                                    # Difference is significant - use calculated (more reliable)
                                    logger.info(
                                        f"[INVOICE TAX VALIDATION] CORRECTING: Using calculated tax_amount={expected_tax_amount:.2f} "
                                        f"instead of extracted={tax_amount:.2f} (difference > tolerance)"
                                    )
                                    tax_amount = expected_tax_amount
                                    extracted_data["tax_rate"] = final_tax_rate
                                else:
                                    # Difference is small - use extracted
                                    logger.info(
                                        f"[INVOICE TAX VALIDATION] Keeping extracted tax_amount={tax_amount:.2f} "
                                        f"(difference <= tolerance)"
                                    )
                                    extracted_data["tax_rate"] = final_tax_rate
                        else:
                            # No tax_rate available - calculate from tax_amount and subtotal
                            extracted_data["tax_rate"] = calculated_tax_rate_from_amount
                            logger.info(
                                f"[INVOICE TAX] No tax_rate found, calculated from amount: {calculated_tax_rate_from_amount}%")

                    if tax_amount is not None:
                        extracted_data["tax_amount"] = tax_amount
                        if tax_confidence is not None:
                            extracted_data["confidence_scores"]["tax_amount"] = tax_confidence

                        # Final fallback: Calculate tax rate if we have subtotal but no tax_rate yet
                        if not extracted_data.get("tax_rate") and extracted_data["subtotal"] and extracted_data["subtotal"] > 0:
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
                                            # Extract currency from CurrencyValue if available
                                            if not currency_extracted and hasattr(price, "currency_code") and price.currency_code:
                                                extracted_data["currency_code"] = str(
                                                    price.currency_code).upper()
                                                currency_extracted = True
                                                logger.info(
                                                    f"[INVOICE CURRENCY] Extracted from UnitPrice CurrencyValue: {extracted_data['currency_code']}")
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
                                            # Extract currency from CurrencyValue if available
                                            if not currency_extracted and hasattr(price, "currency_code") and price.currency_code:
                                                extracted_data["currency_code"] = str(
                                                    price.currency_code).upper()
                                                currency_extracted = True
                                                logger.info(
                                                    f"[INVOICE CURRENCY] Extracted from UnitPrice CurrencyValue: {extracted_data['currency_code']}")
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
                                            # Extract currency from CurrencyValue if available
                                            if not currency_extracted and hasattr(amount, "currency_code") and amount.currency_code:
                                                extracted_data["currency_code"] = str(
                                                    amount.currency_code).upper()
                                                currency_extracted = True
                                                logger.info(
                                                    f"[INVOICE CURRENCY] Extracted from Amount CurrencyValue: {extracted_data['currency_code']}")
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
                                            # Extract currency from CurrencyValue if available
                                            if not currency_extracted and hasattr(amount, "currency_code") and amount.currency_code:
                                                extracted_data["currency_code"] = str(
                                                    amount.currency_code).upper()
                                                currency_extracted = True
                                                logger.info(
                                                    f"[INVOICE CURRENCY] Extracted from Amount CurrencyValue: {extracted_data['currency_code']}")
                                        except (ValueError, TypeError, AttributeError):
                                            pass

                                extracted_data["line_items"].append(line_item)

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
            # Extract currency, tax, and totals from tables first
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

                            # Extract tax rate from table
                            if ("tax" in label or "vat" in label) and "%" in value_str:
                                tax_rate_match = re.search(
                                    r'(\d+(?:\.\d+)?)\s*%', value_str)
                                if tax_rate_match and not extracted_data.get("tax_rate"):
                                    try:
                                        tax_rate_percent = float(
                                            tax_rate_match.group(1))
                                        extracted_data["tax_rate"] = tax_rate_percent
                                    except (ValueError, AttributeError):
                                        pass

                            # Extract total from table
                            if not extracted_data["total_amount"] and "total" in label and "subtotal" not in label:
                                try:
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

                    # Extract currency code - improved extraction with multiple methods
                    if not extracted_data["currency_code"]:
                        # Method 1: Look for "Currency:" label
                        if "currency:" in content_lower:
                            if i + 1 < len(paragraphs):
                                next_para = paragraphs[i + 1].content.strip()
                                if next_para and len(next_para) <= 5:
                                    extracted_data["currency_code"] = next_para.upper(
                                    )
                                    logger.info(
                                        f"[PO CURRENCY] Extracted from label: {extracted_data['currency_code']}")
                        # Method 2: Look for currency codes in the same paragraph
                        elif any(code in content.upper() for code in ["USD", "EUR", "GBP", "JPY", "CAD", "AUD"]):
                            import re
                            currency_match = re.search(
                                r'\b(USD|EUR|GBP|JPY|CAD|AUD)\b', content, re.IGNORECASE)
                            if currency_match:
                                extracted_data["currency_code"] = currency_match.group(
                                    1).upper()
                                logger.info(
                                    f"[PO CURRENCY] Extracted from document text (code): {extracted_data['currency_code']}")
                        # Method 3: Infer from currency symbols (only if no explicit code found)
                        elif not any(code in content.upper() for code in ["USD", "EUR", "GBP"]):
                            if "$" in content and "€" not in content and "£" not in content and "C$" not in content and "A$" not in content:
                                extracted_data["currency_code"] = "USD"
                                logger.info(
                                    f"[PO CURRENCY] Inferred from symbol ($): USD")
                            elif "€" in content:
                                extracted_data["currency_code"] = "EUR"
                                logger.info(
                                    f"[PO CURRENCY] Inferred from symbol (€): EUR")
                            elif "£" in content:
                                extracted_data["currency_code"] = "GBP"
                                logger.info(
                                    f"[PO CURRENCY] Inferred from symbol (£): GBP")
                            elif "C$" in content:
                                extracted_data["currency_code"] = "CAD"
                                logger.info(
                                    f"[PO CURRENCY] Inferred from symbol (C$): CAD")
                            elif "A$" in content:
                                extracted_data["currency_code"] = "AUD"
                                logger.info(
                                    f"[PO CURRENCY] Inferred from symbol (A$): AUD")

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

                    # Extract tax rate (regex fallback)
                    if "tax" in content_lower and "%" in content and not extracted_data.get("tax_rate"):
                        # Try LLM for this specific paragraph
                        if self.llm_extractor.enabled:
                            llm_tax = self.llm_extractor.extract_tax_rate(
                                content)
                            if llm_tax and llm_tax.tax_rate and llm_tax.confidence > 0.7:
                                extracted_data["tax_rate"] = llm_tax.tax_rate
                        else:
                            # Regex fallback
                            tax_rate_match = re.search(
                                r'(\d+(?:\.\d+)?)\s*%', content)
                            if tax_rate_match:
                                try:
                                    tax_rate_percent = float(
                                        tax_rate_match.group(1))
                                    extracted_data["tax_rate"] = tax_rate_percent
                                except (ValueError, AttributeError):
                                    pass

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
            # PHASE 5: Calculate tax_amount from subtotal × tax_rate
            # ============================================================
            # This is DERIVED, not extracted - always accurate if inputs are correct
            subtotal = extracted_data.get("subtotal")
            tax_rate = extracted_data.get("tax_rate")

            if subtotal and tax_rate:
                calculated_tax_amount = subtotal * (tax_rate / 100)

                # If we also extracted tax_amount, validate it
                extracted_tax_amount = extracted_data.get("tax_amount")

                if extracted_tax_amount:
                    # Validate using LLM if available
                    if self.llm_extractor.enabled:
                        # Get relevant paragraphs for context
                        relevant_paragraphs = "\n".join([
                            para.content for para in paragraphs
                            if "tax" in para.content.lower() or "total" in para.content.lower()
                        ]) if hasattr(result, "paragraphs") else ""

                        validation = self.llm_extractor.validate_tax_discrepancy(
                            extracted_tax_amount=extracted_tax_amount,
                            calculated_tax_amount=calculated_tax_amount,
                            subtotal=subtotal,
                            tax_rate=tax_rate,
                            document_context=relevant_paragraphs
                        )

                        if validation and validation.confidence > 0.7:
                            if validation.is_extraction_error:
                                # Use calculated (more reliable)
                                extracted_data["tax_amount"] = calculated_tax_amount
                            else:
                                # Real discrepancy - use extracted but flag
                                extracted_data["tax_amount"] = extracted_tax_amount
                                # Could add a flag here for manual review
                        else:
                            # LLM validation not available or low confidence - use simple validation
                            difference = abs(
                                extracted_tax_amount - calculated_tax_amount)
                            tolerance = subtotal * 0.01  # 1% tolerance
                            if difference <= tolerance:
                                # Close enough - use extracted (might have rounding)
                                extracted_data["tax_amount"] = extracted_tax_amount
                            else:
                                # Too different - use calculated
                                extracted_data["tax_amount"] = calculated_tax_amount
                    else:
                        # No LLM - use simple validation
                        difference = abs(
                            extracted_tax_amount - calculated_tax_amount)
                        tolerance = subtotal * 0.01  # 1% tolerance
                        if difference <= tolerance:
                            extracted_data["tax_amount"] = extracted_tax_amount
                        else:
                            extracted_data["tax_amount"] = calculated_tax_amount
                else:
                    # No extracted tax_amount - use calculated
                    extracted_data["tax_amount"] = calculated_tax_amount

            # ============================================================
            # PHASE 6: Calculate tax_rate from tax_amount if missing
            # ============================================================
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
