from pathlib import Path

from src.constants.llm_prompt_constants import (
    INVOICE_PARSE_PROMPT,
)
from src.schemas.invoice_extraction_schema import (
    InvoiceExtractionSchema,
)
from src.utils.llama_extract_utils import (
    extract_invoice_document,
)
from src.utils.llm_response_utils import (
    call_groq_llm,
    trim_raw_extraction_for_llm,
)


class InvoiceExtractionService:
    def extract_invoice_document(
        self,
        file_path: Path,
    ) -> str:
        return extract_invoice_document(
            file_path,
        )

    def parse_invoice_from_raw(
        self,
        raw_extraction: str,
    ) -> InvoiceExtractionSchema:
        response_text = call_groq_llm(
            f"{INVOICE_PARSE_PROMPT}\n"
            f"{trim_raw_extraction_for_llm(raw_extraction)}",
        )

        extraction = (
            InvoiceExtractionSchema.model_validate_json(
                response_text,
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
