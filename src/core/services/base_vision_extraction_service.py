from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.config.llm_config import (
    GROQ_MODEL_EXTRACTION,
    INVOICE_EXTRACTION_MAX_PDF_PAGES,
)
from src.utils.document_image_utils import (
    build_document_image_data_urls,
)
from src.utils.llm_response_utils import (
    call_groq_vision_llm,
    extract_json_text,
)


class BaseVisionExtractionService:
    def _extract_payload(
        self,
        file_path: Path,
        prompt: str,
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        max_pdf_pages: int | None = None,
    ) -> dict[str, Any]:
        image_data_urls = build_document_image_data_urls(
            file_path,
            max_pdf_pages=(
                max_pdf_pages
                if max_pdf_pages is not None
                else INVOICE_EXTRACTION_MAX_PDF_PAGES
            ),
        )
        response_text = call_groq_vision_llm(
            prompt,
            image_data_urls,
            model=model or GROQ_MODEL_EXTRACTION,
            max_tokens=max_tokens,
        )
        payload = json.loads(
            extract_json_text(
                response_text,
            ),
        )

        if not isinstance(
            payload,
            dict,
        ):
            raise ValueError(
                "Vision extraction returned a non-object JSON payload.",
            )

        return payload
