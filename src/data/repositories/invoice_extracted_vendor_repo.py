from uuid import UUID

from src.data.models.postgres.invoice_extracted_vendor import (
    InvoiceExtractedVendor,
)
from src.data.repositories.base_repo import BaseRepository


class InvoiceExtractedVendorRepository(BaseRepository):
    async def create(
        self,
        invoice_id: UUID,
        vendor_fields: dict,
    ) -> InvoiceExtractedVendor:
        vendor = InvoiceExtractedVendor(
            invoice_id=invoice_id,
            **vendor_fields,
        )

        self.session.add(vendor)

        return vendor
