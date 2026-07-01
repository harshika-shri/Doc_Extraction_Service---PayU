from __future__ import annotations

from pathlib import Path

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
from src.core.services.extraction_confidence_service import (
    ExtractionConfidenceService,
)
from src.core.services.invoice.invoice_extraction_orchestrator import (
    InvoiceExtractionResult,
)
from src.core.services.purchase_order.po_extraction_orchestrator import (
    POExtractionResult,
)
from src.handlers.http_clients.gemini_client import (
    GeminiClient,
)
from src.utils.transient_errors import (
    is_transient_error,
)


class DocumentExtractionPipeline:
    def __init__(
        self,
        *,
        gemini_client: GeminiClient | None = None,
        confidence_service: (
            ExtractionConfidenceService | None
        ) = None,
    ) -> None:
        self.gemini_client = (
            gemini_client
            or GeminiClient()
        )
        self.confidence_service = (
            confidence_service
            or ExtractionConfidenceService(
                gemini_client=self.gemini_client,
            )
        )

    def extract_invoice(
        self,
        file_path: Path,
    ) -> InvoiceExtractionResult:
        payload = self._extract_with_gemini(
            file_path=file_path,
            prompt=INVOICE_GEMINI_EXTRACTION_PROMPT,
        )
        base_result = build_invoice_extraction_result(
            payload,
        )

        try:
            confidence_records, _ = (
                self.confidence_service.score_invoice_extraction(
                    base_result.extraction,
                )
            )
        except LLMServiceError as error:
            print(
                "\nGemini confidence scoring failed; "
                "using per-field extraction confidence. "
                f"Reason: {error.detail}",
            )
            confidence_records = (
                base_result.confidence_records
            )

        result = InvoiceExtractionResult(
            extraction=base_result.extraction,
            confidence_records=confidence_records,
        )
        self._log_invoice_result(
            result,
            path_label="GEMINI",
        )
        return result

    def extract_purchase_order(
        self,
        file_path: Path,
    ) -> POExtractionResult:
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
        print(
            f"Confidence records: {len(result.confidence_records)}",
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
