from __future__ import annotations

import logging

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from src.config.settings import settings

logger = logging.getLogger(__name__)


class SendGridService:
    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
    ) -> None:
        if not settings.SENDGRID_API_KEY:
            raise RuntimeError("SendGrid API key is not configured.")

        if not settings.SENDGRID_FROM_EMAIL:
            raise RuntimeError("SendGrid from email is not configured.")

        message = Mail(
            from_email=settings.SENDGRID_FROM_EMAIL,
            to_emails=to_email,
            subject=subject,
            html_content=html_content,
        )

        try:
            client = SendGridAPIClient(settings.SENDGRID_API_KEY)
            response = client.send(message)
        except Exception:
            logger.exception(
                "SendGrid email delivery failed for recipient=%s",
                to_email,
            )
            raise

        if response.status_code >= 400:
            logger.error(
                "SendGrid returned status=%s for recipient=%s",
                response.status_code,
                to_email,
            )
            raise RuntimeError("Failed to send email via SendGrid.")
