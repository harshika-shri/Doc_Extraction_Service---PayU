from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

from src.core.exceptions.llm_exc import LLMServiceError

_IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
}
_PDF_EXTENSIONS = {".pdf"}
_MAX_PDF_PAGES = 4
_RENDER_DPI = 96


def build_document_image_data_urls(
    file_path: Path,
    *,
    max_pdf_pages: int | None = None,
) -> list[str]:
    suffix = file_path.suffix.lower()

    if suffix in _IMAGE_EXTENSIONS:
        return [
            _encode_image_file(
                file_path,
            ),
        ]

    if suffix in _PDF_EXTENSIONS:
        return _encode_pdf_pages(
            file_path,
            max_pages=max_pdf_pages,
        )

    raise LLMServiceError(
        (
            f"Unsupported document format for vision extraction: "
            f"{suffix or 'unknown'}. Supported formats are "
            "PDF and image files."
        ),
        provider="groq",
        status_code=400,
    )


def _encode_image_file(
    file_path: Path,
) -> str:
    mime_type = (
        mimetypes.guess_type(
            str(file_path),
        )[0]
        or "image/png"
    )
    encoded = base64.b64encode(
        file_path.read_bytes(),
    ).decode(
        "ascii",
    )

    return f"data:{mime_type};base64,{encoded}"


def _encode_pdf_pages(
    file_path: Path,
    *,
    max_pages: int | None = None,
) -> list[str]:
    try:
        import fitz
    except ImportError as error:
        raise LLMServiceError(
            "PyMuPDF is required to process PDF documents.",
            provider="groq",
            status_code=500,
        ) from error

    data_urls: list[str] = []

    with fitz.open(
        file_path,
    ) as document:
        page_count = min(
            len(document),
            max_pages or _MAX_PDF_PAGES,
        )

        for page_index in range(
            page_count,
        ):
            page = document.load_page(
                page_index,
            )
            pixmap = page.get_pixmap(
                dpi=_RENDER_DPI,
            )
            encoded = base64.b64encode(
                pixmap.tobytes(
                    "png",
                ),
            ).decode(
                "ascii",
            )
            data_urls.append(
                f"data:image/png;base64,{encoded}",
            )

    if not data_urls:
        raise LLMServiceError(
            "PDF document did not contain any renderable pages.",
            provider="groq",
            status_code=400,
        )

    return data_urls
