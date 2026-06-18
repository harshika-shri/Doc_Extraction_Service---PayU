from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build

from src.config.settings import settings

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
]


class GmailClient:
    @staticmethod
    def get_service() -> Resource:
        credentials = (
            Credentials.from_authorized_user_file(
                settings.GMAIL_TOKEN_PATH,
                SCOPES,
            )
        )

        return build(
            "gmail",
            "v1",
            credentials=credentials,
        )