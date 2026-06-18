from googleapiclient.discovery import Resource

from src.handlers.gmail.gmail_client import (
    GmailClient,
)


class GmailWatch:
    def __init__(self) -> None:
        self.service: Resource = (
            GmailClient.get_service()
        )

    def start_watch(
        self,
    ) -> dict[str, str]:
        request = {
            "topicName": (
                "projects/"
                "invoice-validation-system/"
                "topics/"
                "gmail-notifications"
            ),
            "labelIds": [
                "INBOX",
            ],
        }

        response = (
            self.service.users()
            .watch(
                userId="me",
                body=request,
            )
            .execute()
        )

        return {
            "history_id": response[
                "historyId"
            ],
            "expiration": response[
                "expiration"
            ],
        }

    def stop_watch(
        self,
    ) -> None:
        (
            self.service.users()
            .stop(
                userId="me",
            )
            .execute()
        )