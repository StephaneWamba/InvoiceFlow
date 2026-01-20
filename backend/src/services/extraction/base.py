"""
Base Extractor Class

Provides common functionality for all document extractors.
"""
from src.services.llm_extractor import LLMExtractor
from .currency_extractor import CurrencyExtractor
from .tax_extractor import TaxExtractor


class BaseExtractor:
    """Base class for document extractors"""

    def __init__(self, llm_extractor: LLMExtractor):
        self.llm_extractor = llm_extractor
        self.currency_extractor = CurrencyExtractor(llm_extractor)
        self.tax_extractor = TaxExtractor(llm_extractor)
