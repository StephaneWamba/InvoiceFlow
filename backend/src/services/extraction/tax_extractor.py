"""
Tax Extraction and Validation Service

Handles tax amount and tax rate extraction with validation logic.
"""
import logging
from typing import Optional, Dict, Any, Tuple

from src.services.llm_extractor import LLMExtractor

logger = logging.getLogger(__name__)


class TaxExtractor:
    """Extracts and validates tax information from documents"""

    def __init__(self, llm_extractor: LLMExtractor):
        self.llm_extractor = llm_extractor

    def extract_and_validate(
        self,
        document_fields: Dict,
        extracted_data: Dict[str, Any],
        azure_result: Any,
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Extract and validate tax amount, tax rate, and subtotal.

        Args:
            document_fields: Azure document fields
            extracted_data: Partially extracted data dict
            azure_result: Azure Form Recognizer result object

        Returns:
            Tuple of (tax_amount, tax_rate, confidence) or (None, None, None)
        """
        # Extract tax amount from Azure fields (if available)
        tax_amount, tax_confidence = self._extract_tax_amount(
            document_fields, extracted_data)

        # If tax_amount already exists in extracted_data (e.g., from LLM), use it
        if tax_amount is None and extracted_data.get("tax_amount"):
            tax_amount = extracted_data["tax_amount"]
            tax_confidence = 0.8  # Default confidence for extracted values

        # Validate tax amount is reasonable
        if tax_amount is not None and extracted_data.get("total_amount"):
            if not self._validate_tax_amount_reasonable(tax_amount, extracted_data["total_amount"]):
                tax_amount = None
                tax_confidence = None

        # Extract and validate tax rate
        if tax_amount is not None and extracted_data.get("subtotal") and extracted_data["subtotal"] > 0:
            tax_rate, final_tax_amount = self._extract_and_validate_tax_rate(
                tax_amount,
                extracted_data["subtotal"],
                document_fields,
                azure_result,
            )

            if tax_rate:
                return final_tax_amount, tax_rate, tax_confidence

        return tax_amount, None, tax_confidence

    def _extract_tax_amount(
        self, document_fields: Dict, extracted_data: Dict[str, Any]
    ) -> Tuple[Optional[float], Optional[float]]:
        """Extract tax amount from Azure fields"""
        tax_amount = None
        tax_confidence = None

        # Try "Tax" field first (most specific)
        if "Tax" in document_fields:
            tax_field = document_fields["Tax"].value
            if tax_field:
                try:
                    tax_amount = float(tax_field.amount)
                    tax_confidence = document_fields["Tax"].confidence
                    logger.info(
                        f"[TAX] Extracted from 'Tax' field: ${tax_amount:.2f} (confidence: {tax_confidence:.2f})"
                    )
                except (ValueError, TypeError, AttributeError) as e:
                    logger.warning(
                        f"[TAX] Failed to extract from 'Tax' field: {e}")

        # Fallback to "TotalTax" field
        if tax_amount is None and "TotalTax" in document_fields:
            tax_field = document_fields["TotalTax"].value
            if tax_field:
                try:
                    tax_amount = float(tax_field.amount)
                    tax_confidence = document_fields["TotalTax"].confidence
                    logger.info(
                        f"[TAX] Extracted from 'TotalTax' field: ${tax_amount:.2f} (confidence: {tax_confidence:.2f})"
                    )
                except (ValueError, TypeError, AttributeError) as e:
                    logger.warning(
                        f"[TAX] Failed to extract from 'TotalTax' field: {e}")

        return tax_amount, tax_confidence

    def _validate_tax_amount_reasonable(self, tax_amount: float, total_amount: float) -> bool:
        """Validate that tax amount is reasonable (not the total amount)"""
        # Tax should be less than total (usually 0-30% of total)
        if tax_amount >= total_amount:
            logger.warning(
                f"[TAX] VALIDATION FAILED: tax_amount (${tax_amount:.2f}) >= total_amount (${total_amount:.2f}). "
                f"This is likely an extraction error - extracted 'Total' instead of 'Tax'"
            )
            return False
        elif tax_amount > total_amount * 0.5:
            logger.warning(
                f"[TAX] VALIDATION WARNING: tax_amount (${tax_amount:.2f}) is >50% of total (${total_amount:.2f}). "
                f"This is unusually high - may be extraction error"
            )
        return True

    def _extract_and_validate_tax_rate(
        self,
        tax_amount: float,
        subtotal: float,
        document_fields: Dict,
        azure_result: Any,
    ) -> Tuple[Optional[float], float]:
        """
        Extract tax rate and validate/correct tax amount.

        Returns:
            Tuple of (tax_rate, final_tax_amount)
        """
        # Calculate tax rate from tax amount and subtotal (ground truth)
        calculated_tax_rate = (tax_amount / subtotal) * 100

        # Get Azure's tax_rate if available (may be wrong)
        azure_tax_rate = self._extract_azure_tax_rate(document_fields)

        # STEP 1: Use LLM to extract tax_rate from document text (most reliable)
        llm_tax_rate = None
        if self.llm_extractor.enabled:
            doc_text = self._get_tax_relevant_text(azure_result)
            if doc_text:
                llm_tax = self.llm_extractor.extract_tax_rate(doc_text)
                if llm_tax and llm_tax.tax_rate and llm_tax.confidence > 0.7:
                    llm_tax_rate = llm_tax.tax_rate
                    logger.info(
                        f"[TAX] LLM extracted tax_rate: {llm_tax_rate}% (confidence: {llm_tax.confidence:.2f})"
                    )

        # STEP 2: Determine which tax_rate to use (priority: LLM > Calculated > Azure)
        final_tax_rate = None
        if llm_tax_rate:
            final_tax_rate = llm_tax_rate
            logger.info(f"[TAX] Using LLM tax_rate: {final_tax_rate}%")
        elif calculated_tax_rate:
            final_tax_rate = calculated_tax_rate
            logger.info(f"[TAX] Using calculated tax_rate: {final_tax_rate}%")
        elif azure_tax_rate:
            final_tax_rate = azure_tax_rate
            logger.warning(
                f"[TAX] Using Azure tax_rate (may be unreliable): {final_tax_rate}%")

        if not final_tax_rate:
            return None, tax_amount

        # STEP 3: Validate and correct tax_amount using the chosen tax_rate
        expected_tax_amount = subtotal * (final_tax_rate / 100)
        difference = abs(tax_amount - expected_tax_amount)
        tolerance = subtotal * 0.01  # 1% tolerance

        # Warn if Azure rate differs significantly
        if azure_tax_rate and abs(azure_tax_rate - final_tax_rate) > 0.5:
            logger.warning(
                f"[TAX] Azure tax_rate ({azure_tax_rate}%) differs from chosen rate ({final_tax_rate}%) - Azure may be wrong"
            )

        # Use LLM validation if available
        if self.llm_extractor.enabled:
            doc_text = self._get_tax_relevant_text(azure_result)
            validation = self.llm_extractor.validate_tax_discrepancy(
                extracted_tax_amount=tax_amount,
                calculated_tax_amount=expected_tax_amount,
                subtotal=subtotal,
                tax_rate=final_tax_rate,
                document_context=doc_text,
            )

            if validation and validation.confidence > 0.7:
                logger.info(
                    f"[TAX VALIDATION] LLM result: is_extraction_error={validation.is_extraction_error}, "
                    f"confidence={validation.confidence:.2f}, reasoning={validation.reasoning[:100]}"
                )
                if validation.is_extraction_error:
                    logger.info(
                        f"[TAX VALIDATION] CORRECTING: Using calculated tax_amount={expected_tax_amount:.2f} "
                        f"instead of extracted={tax_amount:.2f}"
                    )
                    return final_tax_rate, expected_tax_amount
                else:
                    logger.info(
                        f"[TAX VALIDATION] Real discrepancy detected, keeping extracted tax_amount={tax_amount:.2f}"
                    )
                    return final_tax_rate, tax_amount
            elif difference > tolerance:
                logger.warning(
                    f"[TAX VALIDATION] LLM validation failed, but difference={difference:.2f} > tolerance={tolerance:.2f}, using calculated"
                )
                return final_tax_rate, expected_tax_amount
            else:
                # Difference is small - use extracted
                return final_tax_rate, tax_amount
        else:
            # No LLM - use simple validation
            logger.info(
                f"[TAX VALIDATION] LLM not enabled, using simple validation. "
                f"Difference={difference:.2f}, Tolerance={tolerance:.2f}"
            )
            if difference > tolerance:
                logger.info(
                    f"[TAX VALIDATION] CORRECTING: Using calculated tax_amount={expected_tax_amount:.2f} "
                    f"instead of extracted={tax_amount:.2f}"
                )
                return final_tax_rate, expected_tax_amount
            else:
                return final_tax_rate, tax_amount

    def _extract_azure_tax_rate(self, document_fields: Dict) -> Optional[float]:
        """Extract tax rate from Azure TaxRate field"""
        if "TaxRate" not in document_fields:
            return None

        try:
            tax_rate_field = document_fields["TaxRate"].value
            if tax_rate_field:
                # Azure might return as percentage string or number
                if isinstance(tax_rate_field, str):
                    return float(tax_rate_field.replace("%", ""))
                else:
                    # Convert decimal to percentage
                    return float(tax_rate_field) * 100
        except (ValueError, TypeError, AttributeError):
            pass

        return None

    def _get_tax_relevant_text(self, azure_result: Any) -> str:
        """Get text content relevant to tax extraction"""
        if not hasattr(azure_result, "paragraphs"):
            return ""

        doc_text = "\n".join([
            para.content for para in azure_result.paragraphs
            if any(keyword in para.content.lower() for keyword in ["tax", "vat", "total", "subtotal", "%"])
        ])

        return doc_text
