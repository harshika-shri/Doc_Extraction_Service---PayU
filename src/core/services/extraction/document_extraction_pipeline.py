from __future__ import annotations

import json
from pathlib import Path

from src.config.llm_config import (
    GROQ_MODEL_PARSE_INVOICE,
    GROQ_MODEL_PARSE_PO,
)
from src.constants.llm_prompt_constants import (
    INVOICE_PARSE_PROMPT,
    PO_PARSE_PROMPT,
)
from src.constants.prompts.gemini_invoice_extraction_prompt import (
    INVOICE_GEMINI_EXTRACTION_PROMPT,
)
from src.constants.prompts.gemini_po_extraction_prompt import (
    PO_GEMINI_EXTRACTION_PROMPT,
)
from src.core.exceptions.llm_exc import LLMServiceError
from src.core.services.extraction.invoice_extraction_result_assembler import (
    build_invoice_extraction_result,
)
from src.core.services.extraction.po_extraction_result_assembler import (
    build_po_extraction_result,
)
from src.core.services.invoice.invoice_extraction_orchestrator import (
    InvoiceExtractionOrchestrator,
    InvoiceExtractionResult,
)
from src.core.services.purchase_order.po_extraction_orchestrator import (
    POExtractionOrchestrator,
    POExtractionResult,
)
from src.handlers.http_clients.gemini_client import (
    GeminiClient,
)
from src.schemas.invoice_extraction_schema import (
    InvoiceExtractionSchema,
)
from src.schemas.po_extraction_schema import (
    POExtractionSchema,
)
from src.utils.llm_response_utils import (
    call_groq_llm,
    parse_llm_model,
)
from src.utils.pdf_text_utils import (
    extract_embedded_pdf_text,
    has_usable_embedded_text,
)
from src.utils.transient_errors import (
    is_transient_error,
)


class DocumentExtractionPipeline:
    def __init__(
        self,
        *,
        gemini_client: GeminiClient | None = None,
        invoice_vlm_orchestrator: (
            InvoiceExtractionOrchestrator | None
        ) = None,
        po_vlm_orchestrator: (
            POExtractionOrchestrator | None
        ) = None,
    ) -> None:
        self.gemini_client = (
            gemini_client
            or GeminiClient()
        )
        self.invoice_vlm_orchestrator = (
            invoice_vlm_orchestrator
            or InvoiceExtractionOrchestrator()
        )
        self.po_vlm_orchestrator = (
            po_vlm_orchestrator
            or POExtractionOrchestrator()
        )

    def extract_invoice(
        self,
        file_path: Path,
    ) -> InvoiceExtractionResult:
        try:
            payload = self._extract_with_gemini(
                file_path=file_path,
                prompt=INVOICE_GEMINI_EXTRACTION_PROMPT,
            )
            result = build_invoice_extraction_result(
                payload,
            )
            self._log_invoice_result(
                result,
                path_label="GEMINI",
            )
            return result
        except LLMServiceError as error:
            print(
                "\nGemini invoice extraction failed; "
                f"using fallback pipeline. Reason: {error.detail}",
            )
            return self._extract_invoice_fallback(
                file_path,
            )

    def extract_purchase_order(
        self,
        file_path: Path,
    ) -> POExtractionResult:
        try:
            payload = self._extract_with_gemini(
                file_path=file_path,
                prompt=PO_GEMINI_EXTRACTION_PROMPT,
            )
            result = build_po_extraction_result(
                payload,
            )
            self._log_po_result(
                result,
                path_label="GEMINI",
            )
            return result
        except LLMServiceError as error:
            print(
                "\nGemini purchase order extraction failed; "
                f"using fallback pipeline. Reason: {error.detail}",
            )
            return self._extract_po_fallback(
                file_path,
            )

    def _extract_with_gemini(
        self,
        *,
        file_path: Path,
        prompt: str,
    ) -> dict:
        last_error: LLMServiceError | None = None

        for attempt in range(2):
            try:
                return (
                    self.gemini_client.generate_json_from_document(
                        file_path,
                        prompt,
                    )
                )
            except LLMServiceError as error:
                last_error = error

                if (
                    attempt == 0
                    and is_transient_error(
                        error,
                    )
                ):
                    print(
                        "\nRetrying Gemini extraction after "
                        "temporary API failure...",
                    )
                    continue

                raise

        if last_error is not None:
            raise last_error

        raise LLMServiceError(
            "Gemini extraction failed.",
            provider="gemini",
        )

    def _extract_invoice_fallback(
        self,
        file_path: Path,
    ) -> InvoiceExtractionResult:
        extracted_text = extract_embedded_pdf_text(
            file_path,
        )

        if has_usable_embedded_text(
            extracted_text,
        ):
            result = self._structure_invoice_from_text(
                extracted_text,
            )
            self._log_invoice_result(
                result,
                path_label="DIGITAL_PDF_FALLBACK",
            )
            return result

        result = self.invoice_vlm_orchestrator.extract(
            file_path,
        )
        self._log_invoice_result(
            result,
            path_label="SCANNED_VLM_FALLBACK",
        )
        return result

    def _extract_po_fallback(
        self,
        file_path: Path,
    ) -> POExtractionResult:
        extracted_text = extract_embedded_pdf_text(
            file_path,
        )

        if has_usable_embedded_text(
            extracted_text,
        ):
            result = self._structure_po_from_text(
                extracted_text,
            )
            self._log_po_result(
                result,
                path_label="DIGITAL_PDF_FALLBACK",
            )
            return result

        result = self.po_vlm_orchestrator.extract(
            file_path,
        )
        self._log_po_result(
            result,
            path_label="SCANNED_VLM_FALLBACK",
        )
        return result

    def _structure_invoice_from_text(
        self,
        extracted_text: str,
    ) -> InvoiceExtractionResult:
        raw_extraction = json.dumps(
            {
                "full_document_text": extracted_text,
            },
            ensure_ascii=False,
        )
        prompt = (
            f"{INVOICE_PARSE_PROMPT}\n{raw_extraction}"
        )
        response_text = call_groq_llm(
            prompt,
            model=GROQ_MODEL_PARSE_INVOICE,
            max_tokens=4096,
        )
        extraction = parse_llm_model(
            response_text,
            InvoiceExtractionSchema,
        )

        return InvoiceExtractionResult(
            extraction=extraction,
            confidence_records=[],
        )

    def _structure_po_from_text(
        self,
        extracted_text: str,
    ) -> POExtractionResult:
        raw_extraction = json.dumps(
            {
                "full_document_text": extracted_text,
            },
            ensure_ascii=False,
        )
        prompt = (
            f"{PO_PARSE_PROMPT}\n{raw_extraction}"
        )
        response_text = call_groq_llm(
            prompt,
            model=GROQ_MODEL_PARSE_PO,
            max_tokens=4096,
        )
        extraction = parse_llm_model(
            response_text,
            POExtractionSchema,
        )

        return POExtractionResult(
            extraction=extraction,
            confidence_records=[],
        )

    @staticmethod
    def _log_invoice_result(
        result: InvoiceExtractionResult,
        *,
        path_label: str,
    ) -> None:
        print("\n" + "=" * 80)
        print(
            f"INVOICE STRUCTURED EXTRACTION ({path_label})",
        )
        print("=" * 80)
        print(
            result.extraction.model_dump_json(
                indent=2,
            ),
        )

    @staticmethod
    def _log_po_result(
        result: POExtractionResult,
        *,
        path_label: str,
    ) -> None:
        print("\n" + "=" * 80)
        print(
            "PURCHASE ORDER STRUCTURED EXTRACTION "
            f"({path_label})",
        )
        print("=" * 80)
        print(
            result.extraction.model_dump_json(
                indent=2,
            ),
        )
