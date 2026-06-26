from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.constants.document_type import DocumentType
from src.core.exceptions.llm_exc import LLMServiceError
from src.core.exceptions.vendor_master_exc import (
    VendorMasterOnboardingError,
)
from src.core.services.document_classifier_service import (
    DocumentClassifierService,
)
from src.core.services.po_extraction_service import (
    POExtractionService,
)
from src.core.services.vendor_master_service import (
    VendorMasterService,
)
from src.data.models.postgres.purchase_orders import (
    PurchaseOrder,
)
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
    POVendorExtractionSchema,
)
from src.schemas.purchase_order_schema import (
    PurchaseOrderListItem,
    PurchaseOrderListResponse,
    PurchaseOrderUploadResponse,
)
from src.utils.file_utils import (
    save_uploaded_file,
)
from src.utils.tax_details_utils import (
    normalize_tax_details,
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

    DEFAULT_PO_UOM = "EA"

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
        self.classifier_service = (
            DocumentClassifierService()
        )
        self.vendor_master_service = VendorMasterService(
            session,
        )

    async def upload_purchase_order(
        self,
        file: UploadFile,
        current_user: User,
    ) -> PurchaseOrderUploadResponse:
        file_path = await self.stage_purchase_order_upload(
            file,
        )
        purchase_order, line_items_saved = (
            await self.process_saved_purchase_order(
                file_path=str(
                    file_path,
                ),
                company_id=current_user.company_id,
                uploaded_by=current_user.id,
            )
        )

        return PurchaseOrderUploadResponse(
            id=purchase_order.id,
            po_number=purchase_order.po_number,
            po_date=purchase_order.po_date,
            status=purchase_order.status.value,
            gcs_file_path=purchase_order.gcs_file_path,
            line_items_saved=line_items_saved,
        )

    async def stage_purchase_order_upload(
        self,
        file: UploadFile,
    ) -> Path:
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file must have a filename.",
            )

        return await self._save_uploaded_file(
            file,
        )

    async def process_saved_purchase_order(
        self,
        *,
        file_path: str,
        company_id: UUID,
        uploaded_by: UUID,
    ) -> tuple[
        PurchaseOrder,
        int,
    ]:
        path = Path(
            file_path,
        )

        if not path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "Uploaded purchase order file was not found "
                    f"at {file_path}."
                ),
            )

        if await self.file_already_processed(
            file_path,
        ):
            existing = (
                await self.purchase_order_repo.get_by_gcs_file_path(
                    file_path,
                )
            )

            if existing is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=(
                        "Purchase order file was already processed "
                        "but the record could not be loaded."
                    ),
                )

            return existing, 0

        try:
            classification = (
                self.classifier_service.classify_document(
                    path,
                )
            )

            if (
                classification.document_type
                != DocumentType.PURCHASE_ORDER
            ):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        "Uploaded document is not a "
                        "purchase order. "
                        f"Detected type: "
                        f"{classification.document_type.value}."
                    ),
                )

            extraction = (
                self.po_extraction_service.extract_purchase_order(
                    path,
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

        if not payload.line_items:
            if extraction.line_items:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        "Purchase order line items were extracted "
                        "but could not be saved. Check quantity, "
                        "unit price, and line total values."
                    ),
                )

            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "No purchase order line items were extracted "
                    "from the document."
                ),
            )

        purchase_order = (
            await self.save_extracted_purchase_order(
                payload=payload,
                gcs_file_path=file_path,
                company_id=company_id,
                uploaded_by=uploaded_by,
                vendor=extraction.vendor,
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

        return purchase_order, len(
            payload.line_items,
        )

    async def file_already_processed(
        self,
        gcs_file_path: str,
    ) -> bool:
        return (
            await self.purchase_order_repo.exists_for_gcs_file_path(
                gcs_file_path,
            )
        )

    async def po_number_already_exists(
        self,
        po_number: str,
    ) -> bool:
        return (
            await self.purchase_order_repo.exists_for_po_number(
                po_number,
            )
        )

    async def save_extracted_purchase_order(
        self,
        payload: ExtractedPurchaseOrderPayload,
        gcs_file_path: str,
        company_id: UUID,
        uploaded_by: UUID,
        vendor: POVendorExtractionSchema | None = None,
    ) -> PurchaseOrder | None:
        po_number = payload.header_fields.get(
            "po_number",
        )

        if not po_number:
            return None

        if not payload.header_fields.get("po_date"):
            return None

        if await self.file_already_processed(
            gcs_file_path,
        ):
            return (
                await self.purchase_order_repo.get_by_gcs_file_path(
                    gcs_file_path,
                )
            )

        if await self.po_number_already_exists(
            str(po_number),
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Purchase order with number "
                    f"'{po_number}' already exists."
                ),
            )

        try:
            vendor_master = (
                await self.vendor_master_service.resolve_or_create_vendor(
                    vendor,
                    po_number=str(
                        po_number,
                    ),
                )
            )
        except VendorMasterOnboardingError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=error.detail,
            ) from error

        purchase_order = (
            await self.purchase_order_repo.create(
                gcs_file_path=gcs_file_path,
                company_id=company_id,
                uploaded_by=uploaded_by,
                header_fields=payload.header_fields,
            )
        )

        purchase_order.vendor_id = vendor_master.id

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

        for index, line_item in enumerate(
            extraction.line_items,
        ):
            line_values = self._build_line_item_values(
                line_item,
                index=index,
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
        *,
        index: int,
    ) -> dict | None:
        line_number = (
            line_item.line_number
            if line_item.line_number is not None
            else index + 1
        )
        quantity = line_item.quantity_ordered
        unit_price = line_item.unit_price
        line_total = line_item.line_total
        tax_details = normalize_tax_details(
            line_item.tax_details,
        )
        item_description = (
            line_item.item_description
            or line_item.item_code
        )

        has_content = any(
            [
                item_description,
                line_item.item_code,
                quantity is not None,
                unit_price is not None,
                line_total is not None,
            ],
        )

        if not has_content:
            return None

        if (
            line_total is None
            and quantity is not None
            and unit_price is not None
        ):
            line_total = (
                Decimal(
                    str(quantity),
                )
                * Decimal(
                    str(unit_price),
                )
            )

        if (
            quantity is None
            and line_total is not None
            and unit_price is not None
            and unit_price != 0
        ):
            quantity = (
                Decimal(
                    str(line_total),
                )
                / Decimal(
                    str(unit_price),
                )
            )

        if (
            unit_price is None
            and line_total is not None
            and quantity is not None
            and quantity != 0
        ):
            unit_price = (
                Decimal(
                    str(line_total),
                )
                / Decimal(
                    str(quantity),
                )
            )

        if quantity is None:
            quantity = Decimal(
                "1",
            )

        if (
            unit_price is None
            and line_total is not None
        ):
            unit_price = (
                Decimal(
                    str(line_total),
                )
                / quantity
            )

        if (
            line_total is None
            and unit_price is not None
        ):
            line_total = (
                quantity
                * unit_price
            )

        if (
            line_total is None
            or unit_price is None
        ):
            return None

        if not item_description:
            item_description = (
                f"Line {line_number}"
            )

        uom = (
            line_item.uom
            or self.DEFAULT_PO_UOM
        )

        line_values: dict = {
            "line_number": line_number,
            "item_description": item_description,
            "uom": uom,
            "quantity_ordered": quantity,
            "unit_price": unit_price,
            "line_total": line_total,
        }

        for field_name in self.PO_LINE_ITEM_FIELDS:
            if field_name in line_values:
                continue

            value = getattr(
                line_item,
                field_name,
            )

            if value is not None:
                if field_name == "tax_details":
                    line_values[
                        field_name
                    ] = tax_details
                else:
                    line_values[
                        field_name
                    ] = value

        if "discount_amount" not in line_values:
            line_values["discount_amount"] = Decimal(
                "0",
            )

        if tax_details is not None:
            line_values["tax_details"] = tax_details

        return line_values

    def normalize_line_item(
        self,
        line_item: POLineItemExtractionSchema,
        *,
        index: int,
    ) -> dict | None:
        return self._build_line_item_values(
            line_item,
            index=index,
        )

    async def list_purchase_orders(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> PurchaseOrderListResponse:
        purchase_orders, total = (
            await self.purchase_order_repo.list_recent(
                limit=limit,
                offset=offset,
            )
        )

        items = [
            PurchaseOrderListItem(
                id=po.id,
                po_number=po.po_number,
                po_date=po.po_date,
                status=po.status.value
                if hasattr(
                    po.status,
                    "value",
                )
                else str(
                    po.status,
                ),
                total_amount=float(
                    po.total_amount,
                )
                if po.total_amount
                is not None
                else None,
                currency=po.currency,
                created_at=po.created_at,
            )
            for po in purchase_orders
        ]

        return PurchaseOrderListResponse(
            items=items,
            total=total,
        )
