from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.constants.document_type import DocumentType
from src.core.exceptions.llm_exc import LLMServiceError
from src.core.services.document_classifier_service import (
    DocumentClassifierService,
)
from src.core.services.invoice_extraction_service import (
    InvoiceExtractionService,
)
from src.core.services.invoice_service import (
    InvoiceService,
)
from src.data.models.postgres.enums import (
    ExtractionStatus,
)
from src.data.models.postgres.invoices import Invoice
from src.messaging.redis_stream_publisher import (
    queue_extraction_completed,
)
from src.schemas.invoice_upload_schema import (
    InvoiceUploadResponse,
)
from src.utils.extraction_field_utils import (
    identify_review_fields,
)
from src.utils.file_utils import (
    is_processable_attachment,
    save_uploaded_file,
)

_INVOICE_UPLOAD_DIR = "uploads/invoices"
_UPLOAD_FILENAME_PREFIX = "invoice"


class InvoiceUploadService:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self.session = session
        self.classifier_service = (
            DocumentClassifierService()
        )
        self.extraction_service = (
            InvoiceExtractionService()
        )
        self.invoice_service = InvoiceService(
            session,
        )

    async def upload_and_process(
        self,
        file: UploadFile,
    ) -> InvoiceUploadResponse:
        filename = file.filename or "upload"

        if not is_processable_attachment(
            filename,
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Unsupported file type: {Path(filename).suffix}. "
                    "Supported formats: PDF, PNG, JPG, JPEG, TIFF."
                ),
            )

        upload_dir = Path(
            _INVOICE_UPLOAD_DIR,
        )
        prefix = f"{_UPLOAD_FILENAME_PREFIX}_{uuid4().hex[:8]}"
        file_path = await save_uploaded_file(
            file,
            upload_dir,
            filename_prefix=prefix,
        )

        try:
            return await self._classify_and_extract(
                file_path=file_path,
                original_filename=filename,
            )
        except Exception:
            if file_path.exists():
                file_path.unlink(
                    missing_ok=True,
                )
            raise

    async def _classify_and_extract(
        self,
        file_path: Path,
        original_filename: str,
    ) -> InvoiceUploadResponse:
        print(
            "\n"
            + "=" * 80
            + "\nINVOICE UPLOAD PROCESSING STARTED\n"
            + "=" * 80,
        )
        print(
            f"file={original_filename}, "
            f"saved_path={file_path}",
        )

        if await self.invoice_service.attachment_already_processed(
            str(file_path),
        ):
            existing = (
                await self.invoice_service.invoice_repo.get_by_gcs_file_path(
                    str(file_path),
                )
            )

            if existing is not None:
                return InvoiceUploadResponse(
                    invoice_id=existing.id,
                    extraction_status=existing.extraction_status.value,
                    document_type=DocumentType.INVOICE,
                    message="Invoice already processed.",
                )

        try:
            classification = (
                self.classifier_service.classify_document(
                    file_path,
                )
            )
        except LLMServiceError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Classification failed: {exc.detail}",
            ) from exc

        print(
            f"Classification result: "
            f"type={classification.document_type}",
        )

        if (
            classification.document_type
            != DocumentType.INVOICE
        ):
            file_path.unlink(
                missing_ok=True,
            )

            return InvoiceUploadResponse(
                invoice_id=None,
                extraction_status=None,
                document_type=classification.document_type,
                message=(
                    "Document classified as "
                    f"'{classification.document_type}', not an invoice. "
                    "File has been discarded."
                ),
            )

        try:
            extraction_result = (
                self.extraction_service.extract_invoice_with_confidence(
                    file_path,
                )
            )
        except LLMServiceError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Extraction failed: {exc.detail}",
            ) from exc

        confidence_records, has_low_confidence = (
            identify_review_fields(
                extraction_result.confidence_records,
            )
        )

        invoice = (
            await self.invoice_service.save_extracted_invoice(
                extraction=extraction_result.extraction,
                gcs_file_path=str(file_path),
                received_email=None,
                message_id=f"upload_{uuid4().hex}",
                subject=None,
                body_text=None,
                attachment_filename=original_filename,
                confidence_records=confidence_records,
                has_low_confidence=has_low_confidence,
            )
        )

        if (
            invoice.extraction_status
            == ExtractionStatus.EXTRACTION_APPROVED
        ):
            queue_extraction_completed(
                invoice.id,
            )

        print(
            f"Invoice upload complete: "
            f"id={invoice.id}, "
            f"status={invoice.extraction_status.value}",
        )

        return InvoiceUploadResponse(
            invoice_id=invoice.id,
            extraction_status=invoice.extraction_status.value,
            document_type=DocumentType.INVOICE,
            message=(
                "Invoice extracted and saved successfully."
                if not has_low_confidence
                else "Invoice extracted with low confidence fields. Human review required."
            ),
        )
