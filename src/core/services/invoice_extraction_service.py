from pathlib import Path

from src.schemas.invoice_extraction_schema import (
    InvoiceExtractionSchema,
)
from src.utils.llama_document_parser import (
    parse_structured_invoice_llama_extraction,
)
from src.utils.llama_extract_utils import (
    extract_invoice_document,
    extract_structured_invoice_document,
)


class InvoiceExtractionService:
    def extract_invoice_document(
        self,
        file_path: Path,
    ) -> str:
        return extract_invoice_document(
            file_path,
        )

    def extract_invoice_from_file(
        self,
        file_path: Path,
    ) -> InvoiceExtractionSchema:
        raw_extraction = (
            extract_structured_invoice_document(
                file_path,
            )
        )

        extraction = (
            parse_structured_invoice_llama_extraction(
                raw_extraction,
            )
        )

        print("\n" + "=" * 80)
        print("INVOICE STRUCTURED EXTRACTION")
        print("=" * 80)
        print(
            extraction.model_dump_json(
                indent=2,
            ),
        )

        return extraction
