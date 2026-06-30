from __future__ import annotations

import base64
import json
import mimetypes
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from src.config.settings import settings
from src.core.exceptions.llm_exc import LLMServiceError
from src.utils.llm_response_utils import extract_json_text
from src.utils.transient_errors import (
    TRANSIENT_HTTP_STATUS_CODES,
)

_GEMINI_API_BASE_URL = (
    "https://generativelanguage.googleapis.com/v1beta"
)
_IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
}
_PDF_EXTENSIONS = {".pdf"}


class GeminiClient:
    def generate_json_from_document(
        self,
        file_path: Path,
        prompt: str,
        *,
        model: str | None = None,
        max_output_tokens: int = 8192,
        timeout: int = 120,
    ) -> dict[str, Any]:
        selected_model = (
            model or settings.GEMINI_MODEL
        )
        self._validate_configuration()

        request_body = self._build_request_body(
            file_path=file_path,
            prompt=prompt,
            max_output_tokens=max_output_tokens,
        )

        response_payload = self._post_generate_content(
            request_body=request_body,
            model=selected_model,
            timeout=timeout,
        )
        response_text = self._extract_response_text(
            response_payload,
        )

        try:
            payload = json.loads(
                extract_json_text(
                    response_text,
                ),
            )
        except json.JSONDecodeError as error:
            raise LLMServiceError(
                "Gemini extraction returned invalid JSON.",
                provider="gemini",
                status_code=502,
            ) from error

        if not isinstance(
            payload,
            dict,
        ):
            raise LLMServiceError(
                "Gemini extraction returned a non-object JSON payload.",
                provider="gemini",
                status_code=502,
            )

        return payload

    def _validate_configuration(self) -> None:
        if not settings.GEMINI_API_KEY:
            raise LLMServiceError(
                "GEMINI_API_KEY is not configured",
                provider="gemini",
            )

    def _build_request_body(
        self,
        *,
        file_path: Path,
        prompt: str,
        max_output_tokens: int,
    ) -> dict[str, Any]:
        mime_type, encoded_data = (
            self._encode_document(
                file_path,
            )
        )

        return {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                f"{prompt}\n\n"
                                "Return valid JSON only."
                            ),
                        },
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": encoded_data,
                            },
                        },
                    ],
                },
            ],
            "generationConfig": {
                "temperature": 0,
                "maxOutputTokens": max_output_tokens,
                "responseMimeType": "application/json",
            },
        }

    def _encode_document(
        self,
        file_path: Path,
    ) -> tuple[str, str]:
        suffix = file_path.suffix.lower()

        if suffix in _PDF_EXTENSIONS:
            return (
                "application/pdf",
                base64.b64encode(
                    file_path.read_bytes(),
                ).decode(
                    "ascii",
                ),
            )

        if suffix in _IMAGE_EXTENSIONS:
            mime_type = (
                mimetypes.guess_type(
                    str(file_path),
                )[0]
                or "image/png"
            )

            return (
                mime_type,
                base64.b64encode(
                    file_path.read_bytes(),
                ).decode(
                    "ascii",
                ),
            )

        raise LLMServiceError(
            (
                "Unsupported document format for Gemini extraction: "
                f"{suffix or 'unknown'}. Supported formats are "
                "PDF and image files."
            ),
            provider="gemini",
            status_code=400,
        )

    def _post_generate_content(
        self,
        *,
        request_body: dict[str, Any],
        model: str,
        timeout: int,
    ) -> dict[str, Any]:
        url = (
            f"{_GEMINI_API_BASE_URL}/models/"
            f"{model}:generateContent"
            f"?key={settings.GEMINI_API_KEY}"
        )
        request = urllib.request.Request(
            url=url,
            data=json.dumps(
                request_body,
            ).encode(
                "utf-8",
            ),
            headers={
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=timeout,
            ) as response:
                return json.loads(
                    response.read().decode(
                        "utf-8",
                    ),
                )
        except urllib.error.HTTPError as error:
            error_body = error.read().decode(
                "utf-8",
            )

            raise LLMServiceError(
                self._build_error_detail(
                    status_code=error.code,
                    error_body=error_body,
                ),
                provider="gemini",
                status_code=error.code,
            ) from error
        except TimeoutError as error:
            raise LLMServiceError(
                "Gemini API request timed out.",
                provider="gemini",
                status_code=504,
            ) from error
        except urllib.error.URLError as error:
            raise LLMServiceError(
                f"Gemini API network error: {error.reason}",
                provider="gemini",
                status_code=503,
            ) from error

    @staticmethod
    def _extract_response_text(
        response_payload: dict[str, Any],
    ) -> str:
        candidates = response_payload.get(
            "candidates",
            [],
        )

        if not candidates:
            prompt_feedback = response_payload.get(
                "promptFeedback",
            )
            detail = (
                "Gemini response did not contain candidates."
            )

            if isinstance(
                prompt_feedback,
                dict,
            ):
                block_reason = prompt_feedback.get(
                    "blockReason",
                )

                if block_reason:
                    detail = (
                        "Gemini blocked the extraction request: "
                        f"{block_reason}"
                    )

            raise LLMServiceError(
                detail,
                provider="gemini",
                status_code=502,
            )

        content = candidates[0].get(
            "content",
            {},
        )
        parts = content.get(
            "parts",
            [],
        )
        text_parts = [
            str(part.get("text", "")).strip()
            for part in parts
            if isinstance(
                part,
                dict,
            )
            and part.get("text")
        ]

        if not text_parts:
            raise LLMServiceError(
                "Gemini response did not contain text content.",
                provider="gemini",
                status_code=502,
            )

        return "\n".join(
            text_parts,
        )

    @staticmethod
    def _build_error_detail(
        *,
        status_code: int,
        error_body: str,
    ) -> str:
        if status_code in (401, 403):
            return (
                "Gemini API key is invalid or unauthorized."
            )

        if status_code in TRANSIENT_HTTP_STATUS_CODES:
            if error_body.strip():
                return (
                    f"Gemini API temporary failure with HTTP "
                    f"{status_code}: {error_body.strip()}"
                )

            return (
                f"Gemini API temporary failure with HTTP "
                f"{status_code}."
            )

        if error_body.strip():
            return (
                f"Gemini API request failed with HTTP "
                f"{status_code}: {error_body.strip()}"
            )

        return (
            f"Gemini API request failed with HTTP "
            f"{status_code}."
        )
