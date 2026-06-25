from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.constants.extraction_constants import (
    INVOICE_HEADER_FIELDS,
    INVOICE_VENDOR_FIELDS,
)
from src.core.exceptions.extraction_review_exc import (
    ExtractionReviewAccessDeniedError,
    ExtractionReviewNotFoundError,
    ExtractionReviewStateError,
    ExtractionReviewValidationError,
)
from src.core.services.invoice_service import (
    InvoiceService,
)
from src.data.models.postgres.enums import (
    ExtractionStatus,
)
from src.data.models.postgres.invoices import Invoice
from src.data.models.postgres.invoice_extracted_vendor import (
    InvoiceExtractedVendor,
)
from src.data.models.postgres.users import User
from src.data.repositories.audit_log_repo import (
    AuditLogRepository,
)
from src.data.repositories.extraction_review_repo import (
    ExtractionReviewRepository,
)
from src.messaging.redis_stream_publisher import (
    queue_extraction_completed,
)
from src.schemas.extraction_review_schema import (
    BankDetailsReview,
    CompanyDetailsReview,
    ExtractionApproveResponse,
    ExtractionReviewResponse,
    ExtractionUpdateRequest,
    FieldConfidenceReview,
    InvoiceHeaderReview,
    LineItemReview,
    LineItemUpdate,
    VendorDetailsReview,
)
from src.schemas.invoice_extraction_schema import (
    InvoiceLineItemExtractionSchema,
)

LINE_TOTAL_TOLERANCE = Decimal(
    "0.01",
)

BANK_VENDOR_FIELDS = (
    "bank_account_number",
    "bank_name",
    "ifsc_code",
    "account_holder_name",
)

COMPANY_HEADER_FIELDS = (
    "company_name",
    "company_gstin",
    "company_address",
)


class ExtractionReviewService:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self.review_repo = ExtractionReviewRepository(
            session,
        )
        self.audit_log_repo = AuditLogRepository(
            session,
        )
        self.invoice_service = InvoiceService(
            session,
        )

    async def get_review(
        self,
        invoice_id: UUID,
        current_user: User,
    ) -> ExtractionReviewResponse:
        invoice = await self._get_invoice_or_raise(
            invoice_id,
        )
        self._ensure_company_access(
            invoice,
            current_user,
        )

        vendor = await self.review_repo.get_vendor_by_invoice_id(
            invoice_id,
        )
        line_items = await self.review_repo.get_line_items_by_invoice_id(
            invoice_id,
        )
        confidence_scores = (
            await self.review_repo.get_confidence_scores_by_invoice_id(
                invoice_id,
            )
        )

        return self._build_review_response(
            invoice=invoice,
            vendor=vendor,
            line_items=line_items,
            confidence_scores=confidence_scores,
        )

    async def update_extraction(
        self,
        invoice_id: UUID,
        payload: ExtractionUpdateRequest,
        current_user: User,
    ) -> ExtractionReviewResponse:
        invoice = await self._get_invoice_or_raise(
            invoice_id,
        )
        self._ensure_company_access(
            invoice,
            current_user,
        )
        self._ensure_editable(
            invoice,
        )

        header_updates = self._collect_header_updates(
            payload,
        )

        if header_updates:
            await self.review_repo.update_invoice_header_fields(
                invoice,
                header_updates,
            )

        vendor_updates = self._collect_vendor_updates(
            payload,
        )

        if vendor_updates:
            vendor = await self.review_repo.get_vendor_by_invoice_id(
                invoice_id,
            )

            if vendor is None:
                await self.review_repo.create_vendor(
                    invoice_id,
                    vendor_updates,
                )
            else:
                await self.review_repo.update_vendor_fields(
                    vendor,
                    vendor_updates,
                )

        if payload.line_items is not None:
            normalized_line_items = self._normalize_line_items(
                payload.line_items,
            )
            await self.review_repo.replace_line_items(
                invoice_id,
                normalized_line_items,
            )

        await self.audit_log_repo.create(
            invoice_id=invoice_id,
            action="EXTRACTION_EDITED",
            old_status=invoice.extraction_status.value,
            new_status=invoice.extraction_status.value,
            remarks="Extraction fields updated during manual review",
            performed_by=current_user.id,
        )

        return await self.get_review(
            invoice_id,
            current_user,
        )

    async def approve_extraction(
        self,
        invoice_id: UUID,
        current_user: User,
    ) -> ExtractionApproveResponse:
        invoice = await self._get_invoice_or_raise(
            invoice_id,
        )
        self._ensure_company_access(
            invoice,
            current_user,
        )
        self._ensure_approvable(
            invoice,
        )

        line_items = await self.review_repo.get_line_items_by_invoice_id(
            invoice_id,
        )

        if not line_items:
            raise ExtractionReviewValidationError(
                "At least one line item is required before approval",
            )

        self._validate_line_items_for_approval(
            line_items,
        )

        old_status = invoice.extraction_status.value

        await self.review_repo.update_extraction_status(
            invoice,
            ExtractionStatus.EXTRACTION_APPROVED,
        )

        await self.audit_log_repo.create(
            invoice_id=invoice_id,
            action="EXTRACTION_APPROVED",
            old_status=old_status,
            new_status=ExtractionStatus.EXTRACTION_APPROVED.value,
            remarks="Extraction manually approved after review",
            performed_by=current_user.id,
        )

        queue_extraction_completed(
            invoice_id,
        )

        return ExtractionApproveResponse(
            invoice_id=invoice_id,
            extraction_status=ExtractionStatus.EXTRACTION_APPROVED.value,
            message="Extraction approved successfully",
        )

    async def _get_invoice_or_raise(
        self,
        invoice_id: UUID,
    ) -> Invoice:
        invoice = await self.review_repo.get_invoice_by_id(
            invoice_id,
        )

        if invoice is None:
            raise ExtractionReviewNotFoundError(
                str(invoice_id),
            )

        return invoice

    def _ensure_company_access(
        self,
        invoice: Invoice,
        current_user: User,
    ) -> None:
        if (
            invoice.company_id is None
            or invoice.company_id
            != current_user.company_id
        ):
            raise ExtractionReviewAccessDeniedError()

    def _ensure_editable(
        self,
        invoice: Invoice,
    ) -> None:
        if (
            invoice.extraction_status
            == ExtractionStatus.EXTRACTION_APPROVED
        ):
            raise ExtractionReviewStateError(
                "Approved extractions are read-only",
            )

    def _ensure_approvable(
        self,
        invoice: Invoice,
    ) -> None:
        if (
            invoice.extraction_status
            != ExtractionStatus.HUMAN_REVIEW_NEEDED
        ):
            raise ExtractionReviewStateError(
                "Extraction can only be approved when status is "
                f"{ExtractionStatus.HUMAN_REVIEW_NEEDED.value}",
            )

    def _collect_header_updates(
        self,
        payload: ExtractionUpdateRequest,
    ) -> dict[str, Any]:
        updates: dict[str, Any] = {}

        if payload.invoice_header is not None:
            for field_name in INVOICE_HEADER_FIELDS:
                if field_name in COMPANY_HEADER_FIELDS:
                    continue

                value = getattr(
                    payload.invoice_header,
                    field_name,
                )

                if value is not None:
                    updates[field_name] = value

        if payload.company_details is not None:
            for field_name in COMPANY_HEADER_FIELDS:
                value = getattr(
                    payload.company_details,
                    field_name,
                )

                if value is not None:
                    updates[field_name] = value

        return updates

    def _collect_vendor_updates(
        self,
        payload: ExtractionUpdateRequest,
    ) -> dict[str, Any]:
        updates: dict[str, Any] = {}

        if payload.vendor_details is not None:
            for field_name in INVOICE_VENDOR_FIELDS:
                if field_name in BANK_VENDOR_FIELDS:
                    continue

                value = getattr(
                    payload.vendor_details,
                    field_name,
                )

                if value is not None:
                    updates[field_name] = value

        if payload.bank_details is not None:
            for field_name in BANK_VENDOR_FIELDS:
                value = getattr(
                    payload.bank_details,
                    field_name,
                )

                if value is not None:
                    updates[field_name] = value

        return updates

    def _normalize_line_items(
        self,
        line_items: list[LineItemUpdate],
    ) -> list[dict[str, Any]]:
        if not line_items:
            raise ExtractionReviewValidationError(
                "At least one line item is required",
            )

        normalized: list[dict[str, Any]] = []

        for index, line_item in enumerate(
            line_items,
        ):
            schema = InvoiceLineItemExtractionSchema(
                line_number=line_item.line_number,
                item_code=line_item.item_code,
                item_description=line_item.item_description,
                uom=line_item.uom,
                quantity_billed=line_item.quantity_billed,
                unit_price=line_item.unit_price,
                discount_amount=line_item.discount_amount,
                tax_details=line_item.tax_details,
                hsn_sac_code=line_item.hsn_sac_code,
                line_total=line_item.line_total,
            )

            line_values = self.invoice_service.normalize_line_item(
                schema,
                index=index,
            )

            if line_values is None:
                raise ExtractionReviewValidationError(
                    f"Line item {index + 1} is missing required "
                    "quantity, unit price, or line total values",
                )

            self._validate_line_total_consistency(
                line_values,
                line_number=line_values["line_number"],
            )

            normalized.append(
                line_values,
            )

        return normalized

    def _validate_line_items_for_approval(
        self,
        line_items: list[Any],
    ) -> None:
        for line_item in line_items:
            line_values = {
                "line_number": line_item.line_number,
                "quantity_billed": line_item.quantity_billed,
                "unit_price": line_item.unit_price,
                "discount_amount": line_item.discount_amount
                or Decimal(
                    "0",
                ),
                "line_total": line_item.line_total,
            }

            self._validate_line_total_consistency(
                line_values,
                line_number=line_item.line_number,
            )

    def _validate_line_total_consistency(
        self,
        line_values: dict[str, Any],
        *,
        line_number: int,
    ) -> None:
        quantity = Decimal(
            str(
                line_values["quantity_billed"],
            ),
        )
        unit_price = Decimal(
            str(
                line_values["unit_price"],
            ),
        )
        discount = Decimal(
            str(
                line_values.get(
                    "discount_amount",
                    Decimal(
                        "0",
                    ),
                ),
            ),
        )
        line_total = Decimal(
            str(
                line_values["line_total"],
            ),
        )

        expected = (
            quantity * unit_price - discount
        ).quantize(
            Decimal(
                "0.01",
            ),
        )

        if abs(
            expected - line_total,
        ) > LINE_TOTAL_TOLERANCE:
            raise ExtractionReviewValidationError(
                f"Line {line_number}: line total {line_total} does not "
                f"match quantity x unit price - discount ({expected})",
            )

    def _build_review_response(
        self,
        *,
        invoice: Invoice,
        vendor: InvoiceExtractedVendor | None,
        line_items: list[Any],
        confidence_scores: list[Any],
    ) -> ExtractionReviewResponse:
        return ExtractionReviewResponse(
            invoice_id=invoice.id,
            invoice_header=InvoiceHeaderReview(
                invoice_number=invoice.invoice_number,
                invoice_date=invoice.invoice_date,
                po_numbers_extracted=invoice.po_numbers_extracted,
                due_date=invoice.due_date,
                currency=invoice.currency,
                payment_terms=invoice.payment_terms,
                subtotal_amount=invoice.subtotal_amount,
                discount_amount=invoice.discount_amount,
                tax_amount=invoice.tax_amount,
                total_amount=invoice.total_amount,
                notes=invoice.notes,
            ),
            vendor_details=self._map_vendor_details(
                vendor,
            ),
            company_details=CompanyDetailsReview(
                company_name=invoice.company_name,
                company_gstin=invoice.company_gstin,
                company_address=invoice.company_address,
            ),
            bank_details=self._map_bank_details(
                vendor,
            ),
            line_items=[
                LineItemReview(
                    id=item.id,
                    line_number=item.line_number,
                    item_code=item.item_code,
                    item_description=item.item_description,
                    uom=item.uom,
                    quantity_billed=item.quantity_billed,
                    unit_price=item.unit_price,
                    discount_amount=item.discount_amount,
                    tax_details=item.tax_details,
                    hsn_sac_code=item.hsn_sac_code,
                    line_total=item.line_total,
                )
                for item in line_items
            ],
            field_confidence_scores=[
                FieldConfidenceReview(
                    id=record.id,
                    field_name=record.field_name,
                    extracted_value=record.extracted_value,
                    confidence_score=float(
                        record.confidence_score,
                    ),
                    is_flagged=record.is_flagged,
                )
                for record in confidence_scores
            ],
            extraction_status=invoice.extraction_status.value,
        )

    @staticmethod
    def _map_vendor_details(
        vendor: InvoiceExtractedVendor | None,
    ) -> VendorDetailsReview | None:
        if vendor is None:
            return None

        return VendorDetailsReview(
            vendor_name=vendor.vendor_name,
            vendor_gstin=vendor.vendor_gstin,
            vendor_address=vendor.vendor_address,
            vendor_email=vendor.vendor_email,
            vendor_phone=vendor.vendor_phone,
        )

    @staticmethod
    def _map_bank_details(
        vendor: InvoiceExtractedVendor | None,
    ) -> BankDetailsReview | None:
        if vendor is None:
            return None

        return BankDetailsReview(
            bank_account_number=vendor.bank_account_number,
            bank_name=vendor.bank_name,
            ifsc_code=vendor.ifsc_code,
            account_holder_name=vendor.account_holder_name,
        )
