import mimetypes
from email.utils import parseaddr
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from src.constants.extraction_constants import (
    PROCESSABLE_ATTACHMENT_EXTENSIONS,
)


def guess_mime_type(
    file_path: Path,
) -> str:
    mime_type, _ = mimetypes.guess_type(
        file_path.name,
    )

    if mime_type is None:
        return "application/octet-stream"

    return mime_type


def parse_sender_email(
    from_header: str,
) -> str:
    _, email_address = parseaddr(
        from_header,
    )

    if email_address:
        return email_address.strip().lower()

    return from_header.strip()[:255]


def is_processable_attachment(
    filename: str,
) -> bool:
    extension = Path(
        filename,
    ).suffix.lower()

    return extension in PROCESSABLE_ATTACHMENT_EXTENSIONS


def delete_attachment_file(
    file_path: Path,
) -> None:
    if not file_path.exists():
        return

    file_path.unlink()

    parent_dir = file_path.parent

    if (
        parent_dir.exists()
        and not any(
            parent_dir.iterdir(),
        )
    ):
        parent_dir.rmdir()


async def save_uploaded_file(
    file: UploadFile,
    upload_dir: Path,
    filename_prefix: str | None = None,
) -> Path:
    upload_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    original_name = Path(
        file.filename or "upload",
    ).name

    prefix = filename_prefix or str(
        uuid4(),
    )

    file_path = upload_dir / f"{prefix}_{original_name}"

    contents = await file.read()

    file_path.write_bytes(contents)

    return file_path
