from sqlalchemy import func, or_, select

from src.data.models.postgres.company_master import CompanyMaster
from src.data.models.postgres.enums import (
    ExtractionStatus,
    InvoiceStatus,
)
from src.data.models.postgres.invoices import Invoice
from src.data.repositories.base_repo import BaseRepository


class InvoiceRepository(BaseRepository):
    async def exists_for_gcs_file_path(
        self,
        gcs_file_path: str,
    ) -> bool:
        stmt = select(
            Invoice.id,
        ).where(
            Invoice.gcs_file_path
            == gcs_file_path,
        )

        result = await self.execute(stmt)

        return result.scalar_one_or_none() is not None

    async def exists_for_gmail_message_id(
        self,
        gmail_message_id: str,
    ) -> bool:
        path_pattern = (
            f"%/{gmail_message_id}/%"
        )
        stmt = select(
            Invoice.id,
        ).where(
            Invoice.gcs_file_path.ilike(
                path_pattern,
            ),
        )

        result = await self.execute(stmt)

        return result.scalar_one_or_none() is not None

    async def get_by_gcs_file_path(
        self,
        gcs_file_path: str,
    ) -> Invoice | None:
        stmt = select(
            Invoice,
        ).where(
            Invoice.gcs_file_path
            == gcs_file_path,
        )

        result = await self.execute(stmt)

        return result.scalar_one_or_none()

    async def create(
        self,
        gcs_file_path: str,
        received_email: str | None,
        extraction_status: ExtractionStatus,
        header_fields: dict,
    ) -> Invoice:
        invoice = Invoice(
            gcs_file_path=gcs_file_path,
            received_email=received_email,
            extraction_status=extraction_status,
            **header_fields,
        )

        self.session.add(invoice)

        await self.session.flush()

        if invoice.company_id is None:
            company_id = await self._resolve_company_id(
                company_gstin=invoice.company_gstin,
                company_name=invoice.company_name,
            )

            if company_id is not None:
                invoice.company_id = company_id
                await self.session.flush()

        return invoice

    async def flush(self) -> None:
        await self.session.flush()

    async def _resolve_company_id(
        self,
        company_gstin: str | None,
        company_name: str | None,
    ):
        # Only exact matches, and only if it resolves to exactly one company.
        if company_gstin:
            result = await self.execute(
                select(CompanyMaster.id)
                .where(CompanyMaster.gstin == company_gstin)
                .limit(2),
            )
            ids = list(result.scalars().all())
            if len(ids) == 1:
                return ids[0]

        if company_name:
            result = await self.execute(
                select(CompanyMaster.id)
                .where(CompanyMaster.company_name == company_name)
                .limit(2),
            )
            ids = list(result.scalars().all())
            if len(ids) == 1:
                return ids[0]

        return None

    async def list_processing(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Invoice], int]:
        processing_filter = or_(
            Invoice.extraction_status
            != ExtractionStatus.EXTRACTION_APPROVED,
            Invoice.invoice_status
            == InvoiceStatus.UNDER_VALIDATION,
        )

        count_stmt = (
            select(
                func.count(),
            )
            .select_from(
                Invoice,
            )
            .where(
                processing_filter,
            )
        )
        count_result = await self.execute(
            count_stmt,
        )
        total = int(
            count_result.scalar_one(),
        )

        stmt = (
            select(
                Invoice,
            )
            .where(
                processing_filter,
            )
            .order_by(
                Invoice.created_at.desc(),
            )
            .limit(
                limit,
            )
            .offset(
                offset,
            )
        )
        result = await self.execute(
            stmt,
        )

        return (
            list(
                result.scalars().all(),
            ),
            total,
        )
