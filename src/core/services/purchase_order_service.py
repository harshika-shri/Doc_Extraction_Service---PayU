import asyncio
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from src.config.settings import settings
from src.constants.document_type import DocumentType
from src.core.exceptions.client_cancelled_exc import (
    ClientCancelledError,
)
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
from src.core.services.po_vendor_notification_service import (
    POVendorNotificationService,
)
from src.core.services.vendor_master_service import (
    VendorMasterService,
)
from src.data.models.postgres.enums import UserRole
from src.data.models.postgres.purchase_orders import (
    PurchaseOrder,
)
from src.data.models.postgres.users import User
from src.data.repositories.po_line_item_repo import (
    POLineItemRepository,
)
from src.data.repositories.purchase_order_repo import (
    PurchaseOrderDetailRow,
    PurchaseOrderRepository,
)
from src.data.repositories.vendor_master_repo import (
    VendorMasterRow,
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
    PurchaseOrderCompanySummary,
    PurchaseOrderDetailResponse,
    PurchaseOrderLineItemDetail,
    PurchaseOrderListItem,
    PurchaseOrderListResponse,
    PurchaseOrderUploaderSummary,
    PurchaseOrderUploadResponse,
    PurchaseOrderVendorSummary,
)
from src.utils.file_utils import (
    save_uploaded_file,
)
from src.utils.request_cancellation import (
    ensure_client_connected,
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
        self.vendor_notification_service = POVendorNotificationService(
            session,
        )

    async def upload_purchase_order(
        self,
        file: UploadFile,
        current_user: User,
        request: Request | None = None,
    ) -> PurchaseOrderUploadResponse:
        file_path = await self.stage_purchase_order_upload(
            file,
        )

        try:
            await ensure_client_connected(request)

            purchase_order, line_items_saved, line_items_payload, vendor_name, vendor_email = (
                await self.process_saved_purchase_order(
                    file_path=str(
                        file_path,
                    ),
                    company_id=current_user.company_id,
                    uploaded_by=current_user.id,
                    request=request,
                )
            )

            await ensure_client_connected(request)

            if line_items_saved > 0:
                await self.vendor_notification_service.notify_vendor_invoice_required(
                    po_number=purchase_order.po_number,
                    vendor_name=vendor_name,
                    vendor_email=vendor_email,
                    line_items=line_items_payload,
                    uploaded_by=current_user.id,
                )

            return PurchaseOrderUploadResponse(
                id=purchase_order.id,
                po_number=purchase_order.po_number,
                po_date=purchase_order.po_date,
                status=purchase_order.status.value,
                gcs_file_path=purchase_order.gcs_file_path,
                line_items_saved=line_items_saved,
            )
        except ClientCancelledError:
            if file_path.exists() and not await self.file_already_processed(
                str(file_path),
            ):
                file_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=499,
                detail="Upload cancelled.",
            ) from None
        except Exception:
            if file_path.exists() and not await self.file_already_processed(
                str(file_path),
            ):
                file_path.unlink(missing_ok=True)
            raise

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
        request: Request | None = None,
    ) -> tuple[
        PurchaseOrder,
        int,
        list[dict[str, object]],
        str | None,
        str | None,
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

            return existing, 0, [], None, None

        await ensure_client_connected(request)

        try:
            classification = await asyncio.to_thread(
                self.classifier_service.classify_document,
                path,
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

            await ensure_client_connected(request)

            extraction = await asyncio.to_thread(
                self.po_extraction_service.extract_purchase_order,
                path,
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

        await ensure_client_connected(request)

        purchase_order, vendor_master = (
            await self.save_extracted_purchase_order(
                payload=payload,
                gcs_file_path=file_path,
                company_id=company_id,
                uploaded_by=uploaded_by,
                vendor=extraction.vendor,
            )
        )

        if purchase_order is None:
            missing: list[str] = []
            if not payload.header_fields.get("po_number"):
                missing.append("po_number")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Purchase order could not be saved. "
                    f"Missing required field(s): {', '.join(missing) or 'unknown'}."
                ),
            )

        vendor_email = vendor_master.email if vendor_master else None
        vendor_name = vendor_master.vendor_name if vendor_master else None

        return purchase_order, len(
            payload.line_items,
        ), payload.line_items, vendor_name, vendor_email

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
    ) -> tuple[PurchaseOrder | None, VendorMasterRow | None]:
        po_number = payload.header_fields.get(
            "po_number",
        )

        if not po_number:
            return None, None

        if await self.file_already_processed(
            gcs_file_path,
        ):
            existing = (
                await self.purchase_order_repo.get_by_gcs_file_path(
                    gcs_file_path,
                )
            )
            return existing, None

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

        return purchase_order, vendor_master

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

        if not header_fields.get("po_date"):
            header_fields["po_date"] = date.today()

        if not header_fields.get("currency"):
            header_fields["currency"] = "INR"

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
        current_user: User,
        limit: int = 50,
        offset: int = 0,
    ) -> PurchaseOrderListResponse:
        uploaded_by_filter = None
        if current_user.role == UserRole.FINANCE_ASSOCIATE:
            uploaded_by_filter = current_user.id

        purchase_orders, total = await self.purchase_order_repo.list_for_viewer(
            limit=limit,
            offset=offset,
            uploaded_by=uploaded_by_filter,
        )

        items = [
            self._map_list_item(
                po,
                include_uploader=current_user.role == UserRole.FINANCE_MANAGER,
            )
            for po in purchase_orders
        ]

        return PurchaseOrderListResponse(
            items=items,
            total=total,
        )

    async def get_purchase_order_detail(
        self,
        po_id: UUID,
        current_user: User,
    ) -> PurchaseOrderDetailResponse:
        detail = await self.purchase_order_repo.get_detail_by_id(po_id)

        if detail is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Purchase order not found.",
            )

        self._assert_can_access_po(detail, current_user)

        line_items = await self.purchase_order_repo.list_line_items(po_id)

        return self._map_detail_response(
            detail,
            line_items,
            include_uploader=current_user.role == UserRole.FINANCE_MANAGER,
        )

    async def get_purchase_order_file_path(
        self,
        po_id: UUID,
        current_user: User,
    ) -> Path:
        detail = await self.purchase_order_repo.get_detail_by_id(po_id)

        if detail is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Purchase order not found.",
            )

        self._assert_can_access_po(detail, current_user)

        file_path = Path(detail.gcs_file_path)
        if not file_path.is_absolute():
            file_path = Path("/app") / file_path

        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document file not found on server.",
            )

        return file_path

    @staticmethod
    def _assert_can_access_po(
        detail: PurchaseOrderDetailRow,
        current_user: User,
    ) -> None:
        if current_user.role == UserRole.FINANCE_MANAGER:
            return

        if detail.uploaded_by_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this purchase order.",
            )

    @staticmethod
    def _map_uploader(
        *,
        uploaded_by_id: UUID | None,
        uploaded_by_name: str | None,
        uploaded_by_email: str | None,
    ) -> PurchaseOrderUploaderSummary | None:
        if uploaded_by_id is None or uploaded_by_name is None or uploaded_by_email is None:
            return None

        return PurchaseOrderUploaderSummary(
            id=uploaded_by_id,
            name=uploaded_by_name,
            email=uploaded_by_email,
        )

    def _map_list_item(
        self,
        po,
        *,
        include_uploader: bool,
    ) -> PurchaseOrderListItem:
        uploader = None
        if include_uploader:
            uploader = self._map_uploader(
                uploaded_by_id=po.uploaded_by_id,
                uploaded_by_name=po.uploaded_by_name,
                uploaded_by_email=po.uploaded_by_email,
            )

        return PurchaseOrderListItem(
            id=po.id,
            po_number=po.po_number,
            po_date=po.po_date,
            status=po.status.value if hasattr(po.status, "value") else str(po.status),
            total_amount=float(po.total_amount) if po.total_amount is not None else None,
            currency=po.currency,
            created_at=po.created_at,
            uploaded_by=uploader,
        )

    def _map_detail_response(
        self,
        detail: PurchaseOrderDetailRow,
        line_items,
        *,
        include_uploader: bool,
    ) -> PurchaseOrderDetailResponse:
        vendor = None
        if any((detail.vendor_name, detail.vendor_code, detail.vendor_gstin, detail.vendor_email)):
            vendor = PurchaseOrderVendorSummary(
                vendor_name=detail.vendor_name,
                vendor_code=detail.vendor_code,
                gstin=detail.vendor_gstin,
                email=detail.vendor_email,
            )

        company = None
        if any((detail.company_name, detail.company_code, detail.company_gstin)):
            company = PurchaseOrderCompanySummary(
                company_name=detail.company_name,
                company_code=detail.company_code,
                gstin=detail.company_gstin,
            )

        uploader = None
        if include_uploader:
            uploader = self._map_uploader(
                uploaded_by_id=detail.uploaded_by_id,
                uploaded_by_name=detail.uploaded_by_name,
                uploaded_by_email=detail.uploaded_by_email,
            )

        return PurchaseOrderDetailResponse(
            id=detail.id,
            po_number=detail.po_number,
            po_date=detail.po_date,
            valid_until=detail.valid_until,
            status=detail.status.value if hasattr(detail.status, "value") else str(detail.status),
            currency=detail.currency,
            payment_terms=detail.payment_terms,
            delivery_address=detail.delivery_address,
            subtotal_amount=float(detail.subtotal_amount) if detail.subtotal_amount is not None else None,
            discount_amount=float(detail.discount_amount),
            tax_amount=float(detail.tax_amount) if detail.tax_amount is not None else None,
            total_amount=float(detail.total_amount) if detail.total_amount is not None else None,
            consumed_amount=float(detail.consumed_amount),
            created_at=detail.created_at,
            updated_at=detail.updated_at,
            vendor=vendor,
            company=company,
            uploaded_by=uploader,
            line_items=[
                PurchaseOrderLineItemDetail(
                    id=item.id,
                    line_number=item.line_number,
                    item_code=item.item_code,
                    item_description=item.item_description,
                    uom=item.uom,
                    quantity_ordered=float(item.quantity_ordered),
                    unit_price=float(item.unit_price),
                    discount_amount=float(item.discount_amount),
                    line_total=float(item.line_total),
                    consumed_quantity=float(item.consumed_quantity),
                )
                for item in line_items
            ],
        )
