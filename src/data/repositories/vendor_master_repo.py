from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.postgres.enums import VendorStatus
from src.data.models.postgres.vendor_master import VendorMaster
from src.data.repositories.base_repo import BaseRepository


@dataclass(frozen=True, slots=True)
class VendorMasterRow:
    id: UUID
    vendor_code: str
    vendor_name: str
    gstin: str | None
    pan_number: str | None
    email: str | None
    phone: str | None
    address_line_1: str | None
    address_line_2: str | None
    city: str | None
    state: str | None
    bank_name: str | None
    account_number: str | None
    ifsc_code: str | None
    account_holder_name: str | None
    status: VendorStatus


@dataclass(frozen=True, slots=True)
class VendorCreateData:
    vendor_code: str
    vendor_name: str
    gstin: str | None = None
    pan_number: str | None = None
    email: str | None = None
    phone: str | None = None
    address_line_1: str | None = None
    address_line_2: str | None = None
    city: str | None = None
    state: str | None = None
    bank_name: str | None = None
    account_number: str | None = None
    ifsc_code: str | None = None
    account_holder_name: str | None = None


class VendorMasterRepository(BaseRepository):
    async def find_by_vendor_code(
        self,
        vendor_code: str,
    ) -> VendorMasterRow | None:
        result = await self.execute(
            select(
                VendorMaster,
            ).where(
                VendorMaster.vendor_code == vendor_code,
            ),
        )
        vendor = result.scalar_one_or_none()

        if vendor is None:
            return None

        return self._map_vendor(
            vendor,
        )

    async def find_by_gstin(
        self,
        gstin: str,
    ) -> VendorMasterRow | None:
        result = await self.execute(
            select(
                VendorMaster,
            )
            .where(
                VendorMaster.gstin == gstin,
            )
            .limit(
                1,
            ),
        )
        vendor = result.scalar_one_or_none()

        if vendor is None:
            return None

        return self._map_vendor(
            vendor,
        )

    async def find_by_vendor_name(
        self,
        vendor_name: str,
    ) -> VendorMasterRow | None:
        normalized_name = vendor_name.strip().lower()

        if not normalized_name:
            return None

        result = await self.execute(
            select(
                VendorMaster,
            )
            .where(
                func.lower(
                    func.trim(
                        VendorMaster.vendor_name,
                    ),
                )
                == normalized_name,
            )
            .limit(
                2,
            ),
        )
        vendors = list(
            result.scalars().all(),
        )

        if len(vendors) != 1:
            return None

        return self._map_vendor(
            vendors[0],
        )

    async def create_vendor(
        self,
        data: VendorCreateData,
    ) -> VendorMasterRow:
        vendor = VendorMaster(
            vendor_code=data.vendor_code,
            vendor_name=data.vendor_name,
            gstin=data.gstin,
            pan_number=data.pan_number,
            email=data.email,
            phone=data.phone,
            address_line_1=data.address_line_1,
            address_line_2=data.address_line_2,
            city=data.city,
            state=data.state,
            bank_name=data.bank_name,
            account_number=data.account_number,
            ifsc_code=data.ifsc_code,
            account_holder_name=data.account_holder_name,
            status=VendorStatus.ACTIVE,
        )
        self.session.add(
            vendor,
        )
        await self.session.flush()

        return self._map_vendor(
            vendor,
        )

    async def create_vendor_in_savepoint(
        self,
        data: VendorCreateData,
    ) -> VendorMasterRow | None:
        try:
            async with self.session.begin_nested():
                return await self.create_vendor(
                    data,
                )
        except IntegrityError:
            return None

    @staticmethod
    def _map_vendor(
        vendor: VendorMaster,
    ) -> VendorMasterRow:
        return VendorMasterRow(
            id=vendor.id,
            vendor_code=vendor.vendor_code,
            vendor_name=vendor.vendor_name,
            gstin=vendor.gstin,
            pan_number=vendor.pan_number,
            email=vendor.email,
            phone=vendor.phone,
            address_line_1=vendor.address_line_1,
            address_line_2=vendor.address_line_2,
            city=vendor.city,
            state=vendor.state,
            bank_name=vendor.bank_name,
            account_number=vendor.account_number,
            ifsc_code=vendor.ifsc_code,
            account_holder_name=vendor.account_holder_name,
            status=vendor.status,
        )
