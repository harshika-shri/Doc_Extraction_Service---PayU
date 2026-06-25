from __future__ import annotations

import logging
import re
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions.vendor_master_exc import (
    VendorMasterOnboardingError,
)
from src.data.repositories.vendor_master_repo import (
    VendorCreateData,
    VendorMasterRepository,
    VendorMasterRow,
)
from src.schemas.po_extraction_schema import (
    POVendorExtractionSchema,
)

logger = logging.getLogger(
    __name__,
)


class VendorMasterService:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self.vendor_master_repo = VendorMasterRepository(
            session,
        )

    async def resolve_or_create_vendor(
        self,
        vendor: POVendorExtractionSchema | None,
        *,
        po_number: str,
    ) -> VendorMasterRow:
        if vendor is None:
            raise VendorMasterOnboardingError(
                "Vendor details could not be resolved from the purchase order.",
            )

        vendor_data = self._build_vendor_create_data(
            vendor,
        )

        if vendor_data is None:
            raise VendorMasterOnboardingError(
                "Vendor details could not be resolved from the purchase order.",
            )

        existing_vendor = await self._find_existing_vendor(
            vendor,
        )

        if existing_vendor is not None:
            logger.info(
                "Vendor already exists vendor_code=%s vendor_name=%s po_number=%s",
                existing_vendor.vendor_code,
                existing_vendor.vendor_name,
                po_number,
            )
            return existing_vendor

        created_vendor = (
            await self.vendor_master_repo.create_vendor_in_savepoint(
                vendor_data,
            )
        )

        if created_vendor is not None:
            logger.info(
                "Vendor created successfully vendor_code=%s vendor_name=%s po_number=%s",
                created_vendor.vendor_code,
                created_vendor.vendor_name,
                po_number,
            )
            return created_vendor

        existing_vendor = await self._find_existing_vendor(
            vendor,
        )

        if existing_vendor is None:
            existing_vendor = (
                await self.vendor_master_repo.find_by_vendor_code(
                    vendor_data.vendor_code,
                )
            )

        if existing_vendor is not None:
            logger.info(
                "Vendor already exists vendor_code=%s vendor_name=%s po_number=%s",
                existing_vendor.vendor_code,
                existing_vendor.vendor_name,
                po_number,
            )
            return existing_vendor

        raise VendorMasterOnboardingError(
            "Vendor Master record could not be created for this purchase order.",
        )

    async def _find_existing_vendor(
        self,
        vendor: POVendorExtractionSchema,
    ) -> VendorMasterRow | None:
        vendor_code = self._normalize_optional_string(
            vendor.vendor_code,
        )

        if vendor_code is not None:
            existing = await self.vendor_master_repo.find_by_vendor_code(
                vendor_code,
            )

            if existing is not None:
                return existing

        gstin = self._normalize_optional_string(
            vendor.vendor_gstin,
        )

        if gstin is not None:
            existing = await self.vendor_master_repo.find_by_gstin(
                gstin,
            )

            if existing is not None:
                return existing

        vendor_name = self._normalize_optional_string(
            vendor.vendor_name,
        )

        if vendor_name is not None:
            return await self.vendor_master_repo.find_by_vendor_name(
                vendor_name,
            )

        return None

    def _build_vendor_create_data(
        self,
        vendor: POVendorExtractionSchema | None,
    ) -> VendorCreateData | None:
        if vendor is None:
            return None

        vendor_name = self._normalize_optional_string(
            vendor.vendor_name,
        )

        if vendor_name is None:
            return None

        vendor_code = self._normalize_optional_string(
            vendor.vendor_code,
        )
        gstin = self._normalize_optional_string(
            vendor.vendor_gstin,
        )

        if vendor_code is None:
            vendor_code = self._derive_vendor_code(
                vendor_name=vendor_name,
                gstin=gstin,
            )

        return VendorCreateData(
            vendor_code=vendor_code,
            vendor_name=vendor_name,
            gstin=gstin,
            pan_number=self._normalize_optional_string(
                vendor.pan_number,
            ),
            email=self._normalize_optional_string(
                vendor.email,
            ),
            phone=self._normalize_optional_string(
                vendor.phone,
            ),
            address_line_1=self._normalize_optional_string(
                vendor.address_line_1,
            ),
            address_line_2=self._normalize_optional_string(
                vendor.address_line_2,
            ),
            city=self._normalize_optional_string(
                vendor.city,
            ),
            state=self._normalize_optional_string(
                vendor.state,
            ),
            bank_name=self._normalize_optional_string(
                vendor.bank_name,
            ),
            account_number=self._normalize_optional_string(
                vendor.account_number,
            ),
            ifsc_code=self._normalize_optional_string(
                vendor.ifsc_code,
            ),
            account_holder_name=self._normalize_optional_string(
                vendor.account_holder_name,
            ),
        )

    @staticmethod
    def _normalize_optional_string(
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        normalized = value.strip()

        if not normalized:
            return None

        return normalized

    @staticmethod
    def _derive_vendor_code(
        *,
        vendor_name: str,
        gstin: str | None,
    ) -> str:
        if gstin is not None:
            return gstin.upper()

        slug = re.sub(
            r"[^A-Z0-9]+",
            "-",
            vendor_name.upper(),
        ).strip(
            "-",
        )
        suffix = str(
            uuid4(),
        )[:8].upper()

        if slug:
            return f"{slug[:40]}-{suffix}"[:100]

        return f"VND-{suffix}"[:100]
