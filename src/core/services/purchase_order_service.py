from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.core.exceptions.llm_exc import LLMServiceError
from src.core.services.po_extraction_service import (
    POExtractionService,
)
from src.data.models.postgres.purchase_orders import (
    PurchaseOrder,
)
from src.data.models.postgres.vendor_master import VendorMaster
from src.data.models.postgres.users import User
from src.data.repositories.po_line_item_repo import (
    POLineItemRepository,
)
from src.data.repositories.purchase_order_repo import (
    PurchaseOrderRepository,
)
from src.schemas.extraction_persistence_schema import (
    ExtractedPurchaseOrderPayload,
)
from src.schemas.po_extraction_schema import (
    POExtractionSchema,
    POLineItemExtractionSchema,
)
from src.schemas.purchase_order_schema import (
    PurchaseOrderUploadResponse,
)
from src.utils.file_utils import (
    save_uploaded_file,
)


class PurchaseOrderService:
    PO_HEADER_FIELDS = (
        "po_number",
        "delivery_address",
        "currency",
        "payment_terms",
        "po_date",
        "valid_until",
        "subtotal_amount",
        "discount_amount",
        "tax_amount",
        "total_amount",
    )

    PO_LINE_ITEM_FIELDS = (
        "line_number",
        "item_code",
        "item_description",
        "uom",
        "quantity_ordered",
        "unit_price",
        "discount_amount",
        "tax_details",
        "line_total",
    )

    PO_LINE_ITEM_REQUIRED_FIELDS = (
        "line_number",
        "item_description",
        "uom",
        "quantity_ordered",
        "unit_price",
        "line_total",
    )

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self.purchase_order_repo = (
            PurchaseOrderRepository(
                session,
            )
        )
        self.po_line_item_repo = POLineItemRepository(
            session,
        )
        self.po_extraction_service = (
            POExtractionService()
        )

    async def upload_purchase_order(
        self,
        file: UploadFile,
        current_user: User,
    ) -> PurchaseOrderUploadResponse:
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file must have a filename.",
            )

        file_path = await self._save_uploaded_file(
            file,
        )

        try:
            extraction = (
                self.po_extraction_service.extract_purchase_order(
                    file_path,
                )
            )
        except LLMServiceError as error:
            raise HTTPException(
                status_code=error.status_code,
                detail=error.detail,
            ) from error

        payload = self._build_payload(
            extraction,
        )

        purchase_order = (
            await self.save_extracted_purchase_order(
                payload=payload,
                gcs_file_path=str(file_path),
                company_id=current_user.company_id,
                uploaded_by=current_user.id,
                vendor_name=extraction.vendor_name,
                vendor_gstin=extraction.vendor_gstin,
            )
        )

        if purchase_order is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Purchase order could not be saved. "
                    "po_number and po_date are required."
                ),
            )

        return PurchaseOrderUploadResponse(
            id=purchase_order.id,
            po_number=purchase_order.po_number,
            po_date=purchase_order.po_date,
            status=purchase_order.status.value,
            gcs_file_path=purchase_order.gcs_file_path,
            line_items_saved=len(
                payload.line_items,
            ),
        )

    async def save_extracted_purchase_order(
        self,
        payload: ExtractedPurchaseOrderPayload,
        gcs_file_path: str,
        company_id: UUID,
        uploaded_by: UUID,
        vendor_name: str | None = None,
        vendor_gstin: str | None = None,
    ) -> PurchaseOrder | None:
        if not payload.header_fields.get("po_number"):
            return None

        if not payload.header_fields.get("po_date"):
            return None

        vendor_id = await self._resolve_vendor_id(
            vendor_name=vendor_name,
            vendor_gstin=vendor_gstin,
        )

        purchase_order = (
            await self.purchase_order_repo.create(
                gcs_file_path=gcs_file_path,
                company_id=company_id,
                uploaded_by=uploaded_by,
                header_fields=payload.header_fields,
            )
        )

        if vendor_id is not None:
            purchase_order.vendor_id = vendor_id

        for line_item_fields in payload.line_items:
            await self.po_line_item_repo.create(
                po_id=purchase_order.id,
                line_item_fields=line_item_fields,
            )

        await self.purchase_order_repo.flush()

        print(
            f"Purchase order saved: id={purchase_order.id}, "
            f"po_number={purchase_order.po_number}",
        )

        return purchase_order

    async def _resolve_vendor_id(
        self,
        vendor_name: str | None,
        vendor_gstin: str | None,
    ):
        lookup_fields = [
            ("vendor_gstin", vendor_gstin),
            ("vendor_name", vendor_name),
        ]

        for field_name, value in lookup_fields:
            if not value:
                continue

            result = await self.purchase_order_repo.execute(
                select(VendorMaster.id).where(
                    getattr(VendorMaster, field_name) == value,
                ).limit(2),
            )
            ids = list(result.scalars().all())

            if len(ids) == 1:
                return ids[0]

        return None

    async def _save_uploaded_file(
        self,
        file: UploadFile,
    ) -> Path:
        upload_dir = Path(
            settings.PO_UPLOAD_DIR,
        )

        return await save_uploaded_file(
            file=file,
            upload_dir=upload_dir,
            filename_prefix=str(uuid4()),
        )

    def _build_payload(
        self,
        extraction: POExtractionSchema,
    ) -> ExtractedPurchaseOrderPayload:
        header_fields: dict = {}

        for field_name in self.PO_HEADER_FIELDS:
            value = getattr(
                extraction,
                field_name,
            )

            if value is not None:
                header_fields[field_name] = value

        line_items: list[dict] = []

        for line_item in extraction.line_items:
            line_values = self._build_line_item_values(
                line_item,
            )

            if line_values is not None:
                line_items.append(
                    line_values,
                )

        return ExtractedPurchaseOrderPayload(
            header_fields=header_fields,
            line_items=line_items,
        )

    def _build_line_item_values(
        self,
        line_item: POLineItemExtractionSchema,
    ) -> dict | None:
        if not all(
            getattr(line_item, field_name) is not None
            for field_name in self.PO_LINE_ITEM_REQUIRED_FIELDS
        ):
            return None

        line_values: dict = {}

        for field_name in self.PO_LINE_ITEM_FIELDS:
            value = getattr(
                line_item,
                field_name,
            )

            if value is not None:
                line_values[field_name] = value

        if "discount_amount" not in line_values:
            line_values["discount_amount"] = Decimal(
                "0",
            )

        return line_values
