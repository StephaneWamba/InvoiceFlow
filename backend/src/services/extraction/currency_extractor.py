"""
Currency Extraction Service

Consolidates currency extraction logic from multiple fallback methods into
a clean, maintainable service.
"""
import re
import logging
from typing import Optional, List, Any, Dict

from src.services.llm_extractor import LLMExtractor

logger = logging.getLogger(__name__)


class CurrencyExtractor:
    """Extracts currency code from documents using multiple methods"""

    SUPPORTED_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CAD", "AUD"]

    def __init__(self, llm_extractor: LLMExtractor):
        self.llm_extractor = llm_extractor

    def extract(
        self,
        azure_result: Any,
        extracted_data: Dict[str, Any],
        document_fields: Optional[Dict] = None,
    ) -> Optional[str]:
        """
        Extract currency code with priority:
        1. Azure CurrencyValue fields (AmountDue, InvoiceTotal, Total)
        2. Azure CurrencyCode field
        3. LLM extraction (if enabled)
        4. Symbol inference from line items

        Args:
            azure_result: Azure Form Recognizer result object
            extracted_data: Partially extracted data dict (may contain line_items, etc.)
            document_fields: Azure document fields dict (optional, for invoices)

        Returns:
            Currency code (e.g., "USD") or None if not found
        """
        currency_code = None

        # Method 1: Extract from Azure CurrencyValue fields (highest priority)
        if document_fields:
            currency_code = self._extract_from_azure_fields(document_fields)
            if currency_code:
                logger.info(
                    f"[CURRENCY] Extracted from Azure fields: {currency_code}")
                return currency_code

        # Method 2: Extract from Azure CurrencyCode field
        if hasattr(azure_result, "documents") and azure_result.documents:
            for doc in azure_result.documents:
                if hasattr(doc, "fields") and "CurrencyCode" in doc.fields:
                    currency = doc.fields["CurrencyCode"].value
                    if currency:
                        currency_code = str(currency).upper()
                        logger.info(
                            f"[CURRENCY] Extracted from CurrencyCode field: {currency_code}")
                        return currency_code

        # Method 3: LLM extraction (if enabled)
        if self.llm_extractor.enabled:
            currency_code = self._extract_with_llm(
                azure_result, extracted_data)
            if currency_code:
                logger.info(f"[CURRENCY] LLM extracted: {currency_code}")
                return currency_code

        # Method 4: Infer from symbols in line items
        currency_code = self._infer_from_symbols(extracted_data)
        if currency_code:
            logger.info(f"[CURRENCY] Inferred from symbols: {currency_code}")
            return currency_code

        logger.warning(
            "[CURRENCY] Currency extraction failed - no currency found")
        return None

    def _extract_from_azure_fields(self, document_fields: Dict) -> Optional[str]:
        """Extract currency from Azure CurrencyValue fields"""
        # Check AmountDue, InvoiceTotal, Total fields for currency_code
        for field_name in ["AmountDue", "InvoiceTotal", "Total"]:
            if field_name in document_fields:
                field_value = document_fields[field_name].value
                if field_value and hasattr(field_value, "currency_code") and field_value.currency_code:
                    return str(field_value.currency_code).upper()
        return None

    def _extract_with_llm(
        self, azure_result: Any, extracted_data: Dict[str, Any]
    ) -> Optional[str]:
        """Extract currency using LLM from document text"""
        # Collect text from multiple sources
        text_content = self._collect_text_content(azure_result, extracted_data)

        if not text_content:
            return None

        # Use LLM extraction
        llm_currency = self.llm_extractor.extract_currency(text_content)
        if llm_currency and llm_currency.currency_code and llm_currency.confidence > 0.7:
            return llm_currency.currency_code.upper()

        # Fallback: regex on collected text
        return self._extract_with_regex(text_content)

    def _collect_text_content(
        self, azure_result: Any, extracted_data: Dict[str, Any]
    ) -> str:
        """Collect text content from various sources for currency extraction"""
        text_parts = []

        # From paragraphs
        if hasattr(azure_result, "paragraphs") and azure_result.paragraphs:
            text_parts.extend(
                [para.content for para in azure_result.paragraphs[:20]])

        # From pages (alternative structure)
        if not text_parts and hasattr(azure_result, "pages") and azure_result.pages:
            for page in azure_result.pages:
                if hasattr(page, "paragraphs"):
                    text_parts.extend(
                        [para.content for para in page.paragraphs])

        # From document fields
        if hasattr(azure_result, "documents") and azure_result.documents:
            for doc in azure_result.documents:
                if hasattr(doc, "fields"):
                    for field_name, field_value in doc.fields.items():
                        if field_value and hasattr(field_value, "value"):
                            field_str = str(field_value.value)
                            if field_str:
                                text_parts.append(field_str)

        # From line items
        for item in extracted_data.get("line_items", []):
            if item.get("description"):
                text_parts.append(str(item["description"]))
            if item.get("unit_price"):
                text_parts.append(str(item["unit_price"]))

        # From already extracted fields
        for field in ["vendor_name", "invoice_number", "total_amount"]:
            if extracted_data.get(field):
                text_parts.append(str(extracted_data[field]))

        return "\n".join(text_parts[:50])  # Limit to first 50 segments

    def _extract_with_regex(self, text: str) -> Optional[str]:
        """Extract currency code using regex patterns"""
        if not text:
            return None

        currency_patterns = [
            r'\b(USD|EUR|GBP|JPY|CAD|AUD)\b',
            r'Currency[:\s]+([A-Z]{3})',
            r'([A-Z]{3})\s+Currency',
        ]

        for pattern in currency_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                currency_code = match.group(1).upper()
                if currency_code in self.SUPPORTED_CURRENCIES:
                    return currency_code

        return None

    def _infer_from_symbols(self, extracted_data: Dict[str, Any]) -> Optional[str]:
        """Infer currency from symbols in line item prices"""
        # Check line items for currency symbols
        for item in extracted_data.get("line_items", []):
            price_str = ""
            if item.get("unit_price"):
                price_str = str(item["unit_price"])
            elif item.get("line_total"):
                price_str = str(item["line_total"])

            if price_str:
                # Check for currency symbols (order matters - EUR before USD)
                if "€" in price_str or "EUR" in price_str.upper():
                    return "EUR"
                elif "£" in price_str or "GBP" in price_str.upper():
                    return "GBP"
                elif "C$" in price_str:
                    return "CAD"
                elif "A$" in price_str:
                    return "AUD"
                elif "$" in price_str:
                    return "USD"

        # Check collected text content for symbols
        text_content = ""
        for field in ["vendor_name", "invoice_number", "total_amount"]:
            if extracted_data.get(field):
                text_content += str(extracted_data[field]) + " "

        if text_content:
            text_upper = text_content.upper()
            if "€" in text_content or "EUR" in text_upper or "EURO" in text_upper:
                return "EUR"
            elif "£" in text_content or "GBP" in text_upper:
                return "GBP"
            elif "$" in text_content and "C$" not in text_content and "A$" not in text_content:
                return "USD"
            elif "C$" in text_content:
                return "CAD"
            elif "A$" in text_content:
                return "AUD"

        return None
