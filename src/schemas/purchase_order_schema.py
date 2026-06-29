from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class PurchaseOrderUploadResponse(BaseModel):
    id: UUID
    po_number: str
    po_date: date
    status: str
    gcs_file_path: str
    line_items_saved: int


class PurchaseOrderUploaderSummary(BaseModel):
    id: UUID
    name: str
    email: str


class PurchaseOrderListItem(BaseModel):
    id: UUID
    po_number: str
    po_date: date
    status: str
    total_amount: float | None
    currency: str
    created_at: datetime | None = None
    uploaded_by: PurchaseOrderUploaderSummary | None = None


class PurchaseOrderListResponse(BaseModel):
    items: list[PurchaseOrderListItem]
    total: int


class PurchaseOrderVendorSummary(BaseModel):
    vendor_name: str | None = None
    vendor_code: str | None = None
    gstin: str | None = None
    email: str | None = None


class PurchaseOrderCompanySummary(BaseModel):
    company_name: str | None = None
    company_code: str | None = None
    gstin: str | None = None


class PurchaseOrderLineItemDetail(BaseModel):
    id: UUID
    line_number: int
    item_code: str | None
    item_description: str
    uom: str
    quantity_ordered: float
    unit_price: float
    discount_amount: float | None
    line_total: float
    consumed_quantity: float


class PurchaseOrderDetailResponse(BaseModel):
    id: UUID
    po_number: str
    po_date: date
    valid_until: date | None
    status: str
    currency: str
    payment_terms: str | None
    delivery_address: str | None
    subtotal_amount: float | None
    discount_amount: float | None
    tax_amount: float | None
    total_amount: float | None
    consumed_amount: float
    created_at: datetime | None
    updated_at: datetime | None
    vendor: PurchaseOrderVendorSummary | None = None
    company: PurchaseOrderCompanySummary | None = None
    uploaded_by: PurchaseOrderUploaderSummary | None = None
    line_items: list[PurchaseOrderLineItemDetail]
