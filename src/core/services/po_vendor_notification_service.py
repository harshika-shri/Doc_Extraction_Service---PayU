from __future__ import annotations

import html
import logging
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.services.sendgrid_service import SendGridService
from src.data.repositories.notification_repo import NotificationRepository

logger = logging.getLogger(__name__)


class POVendorNotificationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.sendgrid_service = SendGridService()
        self.notification_repo = NotificationRepository(session)

    async def notify_vendor_invoice_required(
        self,
        *,
        po_number: str,
        vendor_name: str | None,
        vendor_email: str | None,
        line_items: list[dict[str, object]],
        uploaded_by: UUID,
    ) -> None:
        item_lines = self._format_line_items(line_items)
        vendor_display = vendor_name or "Vendor"

        if vendor_email:
            subject = f"Invoice required for Purchase Order {po_number}"
            html_content = (
                f"<p>Dear {html.escape(vendor_display)},</p>"
                "<p>Thank you for your continued partnership. "
                "Our records show that the following purchase order "
                "has been registered and is awaiting your invoice.</p>"
                f"<p><strong>Purchase Order:</strong> {html.escape(po_number)}</p>"
                "<p><strong>Line items on this PO:</strong></p>"
                f"<ul>{item_lines}</ul>"
                "<p>Please submit the corresponding tax invoice at your "
                "earliest convenience, referencing the PO number above. "
                "If you have already sent the invoice, kindly disregard "
                "this message.</p>"
                "<p>Regards,<br/>Accounts Payable Team<br/>PayU Finance</p>"
            )

            try:
                self.sendgrid_service.send_email(
                    to_email=vendor_email,
                    subject=subject,
                    html_content=html_content,
                )
                notification_message = (
                    f"Invoice request email sent to {vendor_email} "
                    f"for PO {po_number}."
                )
            except Exception:
                logger.exception(
                    "Failed to send PO invoice request email for po=%s",
                    po_number,
                )
                notification_message = (
                    f"PO {po_number} saved, but the vendor email "
                    f"could not be delivered to {vendor_email}."
                )
        else:
            notification_message = (
                f"PO {po_number} saved. No vendor email on file — "
                "invoice request was not sent."
            )

        await self.notification_repo.create(
            user_id=uploaded_by,
            invoice_id=None,
            title="PO vendor email sent",
            message=notification_message,
        )

    @staticmethod
    def _format_line_items(
        line_items: list[dict[str, object]],
    ) -> str:
        if not line_items:
            return "<li>No line items listed</li>"

        rows: list[str] = []
        for item in line_items:
            description = html.escape(
                str(
                    item.get("item_description")
                    or item.get("item_code")
                    or "Item",
                ),
            )
            code = item.get("item_code")
            qty = item.get("quantity_ordered")
            qty_text = ""
            if isinstance(qty, (int, float, Decimal)):
                qty_text = f" — Qty: {qty}"

            code_text = ""
            if code:
                code_text = f" ({html.escape(str(code))})"

            rows.append(
                f"<li>{description}{code_text}{qty_text}</li>",
            )

        return "".join(rows)
