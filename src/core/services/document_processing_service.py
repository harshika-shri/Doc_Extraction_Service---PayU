from pathlib import Path

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.constants.document_type import DocumentType
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
from src.messaging.redis_stream_publisher import (
    queue_extraction_completed,
)
from src.schemas.gmail_message_schema import (
    GmailAttachmentSchema,
    GmailMessageSchema,
)
from src.utils.extraction_field_utils import (
    identify_review_fields,
)
from src.utils.file_utils import (
    delete_attachment_file,
    is_processable_attachment,
)

logger = logging.getLogger(__name__)


class DocumentProcessingService:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self.session = session
        self.classifier_service = (
            DocumentClassifierService()
        )
        self.invoice_extraction_service = (
            InvoiceExtractionService()
        )
        self.invoice_service = InvoiceService(
            session,
        )

    async def process_message_attachments(
        self,
        message: GmailMessageSchema,
    ) -> None:
        processable_attachments = [
            attachment
            for attachment in message.attachments
            if is_processable_attachment(
                attachment.filename,
            )
        ]

        if not processable_attachments:
            print(
                "\nSkipping document "
                "processing: no processable "
                "attachments.",
            )
            return

        print("\n" + "=" * 80)
        print("DOCUMENT PROCESSING STARTED")
        print("=" * 80)
        print(
            f"Message ID: "
            f"{message.message_id}",
        )

        for attachment in processable_attachments:
            await self._process_attachment(
                attachment=attachment,
                message=message,
            )

    async def _process_attachment(
        self,
        attachment: GmailAttachmentSchema,
        message: GmailMessageSchema,
    ) -> None:
        file_path = Path(
            attachment.file_path,
        )

        if not file_path.exists():
            print(
                f"Attachment not found, "
                f"skipping: {file_path}",
            )
            return

        if await self.invoice_service.attachment_already_processed(
            str(file_path),
        ):
            print(
                "Skipping already saved attachment: "
                f"{attachment.filename}",
            )
            return

        classification = (
            self.classifier_service.classify_document(
                file_path,
            )
        )

        if (
            classification.document_type
            != DocumentType.INVOICE
        ):
            if not DocumentClassifierService.is_supported_document_type(
                classification.document_type,
            ):
                print(
                    f"Unsupported document type. "
                    f"Deleting attachment: "
                    f"{file_path}",
                )
                delete_attachment_file(
                    file_path,
                )
                return

            print(
                f"Skipping non-invoice attachment "
                f"from email: {file_path}. "
                "Purchase orders must be uploaded "
                "via the purchase order endpoint.",
            )
            delete_attachment_file(
                file_path,
            )
            return

        extraction_result = (
            self.invoice_extraction_service.extract_invoice_with_confidence(
                file_path,
            )
        )

        confidence_records, has_low_confidence = (
            identify_review_fields(
                extraction_result.confidence_records,
            )
        )

        invoice = await self.invoice_service.save_extracted_invoice(
            extraction=extraction_result.extraction,
            gcs_file_path=str(file_path),
            received_email=message.sender_email,
            message_id=message.message_id,
            subject=message.subject,
            body_text=message.body,
            attachment_filename=attachment.filename,
            confidence_records=confidence_records,
            has_low_confidence=has_low_confidence,
        )

        if (
            invoice.extraction_status
            == ExtractionStatus.EXTRACTION_APPROVED
        ):
            queue_extraction_completed(
                invoice.id,
            )
            logger.info(
                "Queued extraction.completed event invoice_id=%s",
                invoice.id,
            )
        else:
            logger.info(
                "Extraction requires human review before validation; "
                "invoice_id=%s status=%s",
                invoice.id,
                invoice.extraction_status.value,
            )

        print(
            f"Invoice processing completed for: "
            f"{attachment.filename}",
        )
