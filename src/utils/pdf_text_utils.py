from __future__ import annotations

import re
from pathlib import Path

from src.config.llm_config import (
    PDF_MIN_USABLE_TEXT_CHARS,
    PDF_MIN_USABLE_TEXT_RATIO,
)
from src.core.exceptions.llm_exc import LLMServiceError

_PDF_EXTENSIONS = {".pdf"}
_WHITESPACE_PATTERN = re.compile(
    r"\s+",
)


def extract_embedded_pdf_text(
    file_path: Path,
) -> str:
    if file_path.suffix.lower() not in _PDF_EXTENSIONS:
        return ""

    try:
        import fitz
    except ImportError as error:
        raise LLMServiceError(
            "PyMuPDF is required to extract PDF text.",
            provider="groq",
            status_code=500,
        ) from error

    text_parts: list[str] = []

    with fitz.open(
        file_path,
    ) as document:
        for page_index in range(
            len(document),
        ):
            page = document.load_page(
                page_index,
            )
            page_text = page.get_text(
                "text",
            ).strip()

            if page_text:
                text_parts.append(
                    page_text,
                )

    return _WHITESPACE_PATTERN.sub(
        " ",
        "\n".join(
            text_parts,
        ),
    ).strip()


def has_usable_embedded_text(
    text: str,
) -> bool:
    normalized = text.strip()

    if len(
        normalized,
    ) < PDF_MIN_USABLE_TEXT_CHARS:
        return False

    alnum_count = sum(
        1
        for character in normalized
        if character.isalnum()
    )

    if alnum_count == 0:
        return False

    ratio = alnum_count / len(
        normalized,
    )

    return ratio >= PDF_MIN_USABLE_TEXT_RATIO
