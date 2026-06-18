from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from src.constants.document_type import DocumentType
from src.core.services.document_classification_service import (
    DocumentClassificationService,
)
from src.core.services.invoice_extraction_service import (
    InvoiceExtractionService,
)
from src.core.services.invoice_service import (
    InvoiceService,
)
from src.schemas.gmail_message_schema import (
    GmailAttachmentSchema,
    GmailMessageSchema,
)
from src.utils.file_utils import (
    delete_attachment_file,
    is_processable_attachment,
)
from src.utils.llama_extract_utils import (
    extract_invoice_document,
)


class DocumentProcessingService:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self.session = session
        self.classification_service = (
            DocumentClassificationService()
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

        raw_extraction = (
            extract_invoice_document(
                file_path,
            )
        )

        classification = (
            self.classification_service.classify_from_raw(
                raw_extraction,
            )
        )

        if (
            classification.document_type
            != DocumentType.INVOICE
        ):
            if not DocumentClassificationService.is_supported_document_type(
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

        extraction = (
            self.invoice_extraction_service.parse_invoice_from_raw(
                raw_extraction,
            )
        )

        await self.invoice_service.save_extracted_invoice(
            extraction=extraction,
            gcs_file_path=str(file_path),
            received_email=message.sender_email,
        )

        print(
            f"Invoice processing completed for: "
            f"{attachment.filename}",
        )
