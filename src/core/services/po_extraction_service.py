from pathlib import Path

from src.schemas.po_extraction_schema import (
    POExtractionSchema,
)
from src.utils.llama_extract_utils import (
    extract_purchase_order_document,
)
from src.utils.llama_document_parser import (
    parse_po_llama_extraction,
)


class POExtractionService:
    def extract_purchase_order(
        self,
        file_path: Path,
    ) -> POExtractionSchema:
        raw_extraction = (
            extract_purchase_order_document(
                file_path,
            )
        )

        return self.parse_purchase_order_from_raw(
            raw_extraction,
        )

    def parse_purchase_order_from_raw(
        self,
        raw_extraction: str,
    ) -> POExtractionSchema:
        extraction = parse_po_llama_extraction(
            raw_extraction,
        )

        print("\n" + "=" * 80)
        print("PURCHASE ORDER STRUCTURED EXTRACTION")
        print("=" * 80)
        print(
            extraction.model_dump_json(
                indent=2,
            ),
        )

        return extraction
