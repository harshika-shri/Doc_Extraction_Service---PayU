import base64
from pathlib import Path
from typing import Any

from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError

from src.core.exceptions.gmail_exc import (
    GmailHistoryStaleError,
)

from src.schemas.gmail_message_schema import (
    GmailAttachmentSchema,
    GmailMessageSchema,
)
from src.utils.file_utils import (
    is_processable_attachment,
    parse_sender_email,
)


class GmailMessageHandler:
    def __init__(
        self,
        service: Resource,
        attachment_download_dir: Path,
    ) -> None:
        self.service = service
        self.attachment_download_dir = (
            attachment_download_dir
        )

    def get_message_ids_from_history(
        self,
        start_history_id: int,
    ) -> list[str]:
        message_ids: list[str] = []
        page_token: str | None = None

        try:
            while True:
                request_kwargs: dict[
                    str,
                    Any,
                ] = {
                    "userId": "me",
                    "startHistoryId": (
                        start_history_id
                    ),
                    "historyTypes": [
                        "messageAdded",
                    ],
                }

                if page_token is not None:
                    request_kwargs[
                        "pageToken"
                    ] = page_token

                history_response = (
                    self.service.users()
                    .history()
                    .list(
                        **request_kwargs,
                    )
                    .execute()
                )

                for history_record in history_response.get(
                    "history",
                    [],
                ):
                    for message_added in history_record.get(
                        "messagesAdded",
                        [],
                    ):
                        message_id = (
                            message_added[
                                "message"
                            ]["id"]
                        )

                        if (
                            message_id
                            not in message_ids
                        ):
                            message_ids.append(
                                message_id,
                            )

                page_token = (
                    history_response.get(
                        "nextPageToken",
                    )
                )

                if page_token is None:
                    break
        except HttpError as error:
            if error.resp.status == 404:
                print(
                    "Gmail history ID is stale. "
                    "A mailbox resync is required before "
                    "processing new mail.",
                )
                raise GmailHistoryStaleError(
                    "Gmail history cursor is stale.",
                ) from error

            raise

        return message_ids

    def get_inbox_message_ids_for_recovery(
        self,
        *,
        max_results: int = 100,
    ) -> list[str]:
        message_ids: list[str] = []
        page_token: str | None = None

        while len(
            message_ids,
        ) < max_results:
            request_kwargs: dict[
                str,
                Any,
            ] = {
                "userId": "me",
                "labelIds": [
                    "INBOX",
                ],
                "maxResults": min(
                    50,
                    max_results
                    - len(
                        message_ids,
                    ),
                ),
            }

            if page_token is not None:
                request_kwargs[
                    "pageToken"
                ] = page_token

            response = (
                self.service.users()
                .messages()
                .list(
                    **request_kwargs,
                )
                .execute()
            )

            for message in response.get(
                "messages",
                [],
            ):
                message_id = message.get(
                    "id",
                )

                if (
                    message_id
                    and message_id
                    not in message_ids
                ):
                    message_ids.append(
                        str(
                            message_id,
                        ),
                    )

            page_token = response.get(
                "nextPageToken",
            )

            if page_token is None:
                break

        message_ids.reverse()

        return message_ids

    def get_mailbox_history_id(
        self,
    ) -> int:
        profile = (
            self.service.users()
            .getProfile(
                userId="me",
            )
            .execute()
        )

        return int(
            profile[
                "historyId"
            ],
        )

    def fetch_message(
        self,
        message_id: str,
    ) -> GmailMessageSchema:
        message_response = (
            self.service.users()
            .messages()
            .get(
                userId="me",
                id=message_id,
                format="full",
            )
            .execute()
        )

        payload = message_response[
            "payload"
        ]

        subject = self._extract_header(
            payload,
            "Subject",
        )

        sender_email = parse_sender_email(
            self._extract_header(
                payload,
                "From",
            ),
        )

        body = self._extract_body(
            payload,
        )

        attachments = (
            self._download_attachments(
                message_id=message_id,
                payload=payload,
            )
        )

        return GmailMessageSchema(
            message_id=message_id,
            subject=subject,
            body=body,
            sender_email=sender_email or None,
            attachments=attachments,
        )

    def _extract_header(
        self,
        payload: dict[
            str,
            Any,
        ],
        header_name: str,
    ) -> str:
        for header in payload.get(
            "headers",
            [],
        ):
            if (
                header.get(
                    "name",
                )
                == header_name
            ):
                return str(
                    header.get(
                        "value",
                        "",
                    )
                )

        return ""

    def _extract_body(
        self,
        payload: dict[
            str,
            Any,
        ],
    ) -> str:
        plain_text = (
            self._find_body_part(
                payload,
                "text/plain",
            )
        )

        if plain_text:
            return plain_text

        html_text = (
            self._find_body_part(
                payload,
                "text/html",
            )
        )

        if html_text:
            return html_text

        body_data = payload.get(
            "body",
            {},
        ).get(
            "data",
        )

        if body_data:
            return self._decode_base64url(
                str(body_data),
            )

        return ""

    def _find_body_part(
        self,
        payload: dict[
            str,
            Any,
        ],
        mime_type: str,
    ) -> str:
        if payload.get(
            "mimeType",
        ) == mime_type:
            body_data = payload.get(
                "body",
                {},
            ).get(
                "data",
            )

            if body_data:
                return self._decode_base64url(
                    str(body_data),
                )

        for part in payload.get(
            "parts",
            [],
        ):
            body_text = (
                self._find_body_part(
                    part,
                    mime_type,
                )
            )

            if body_text:
                return body_text

        return ""

    def _download_attachments(
        self,
        message_id: str,
        payload: dict[
            str,
            Any,
        ],
    ) -> list[
        GmailAttachmentSchema
    ]:
        self.attachment_download_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        message_dir = (
            self.attachment_download_dir
            / message_id
        )

        message_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        downloaded_attachments: list[
            GmailAttachmentSchema
        ] = []

        for part in self._iter_parts(
            payload,
        ):
            filename = part.get(
                "filename",
            )

            attachment_id = part.get(
                "body",
                {},
            ).get(
                "attachmentId",
            )

            if (
                not filename
                or not attachment_id
            ):
                continue

            if not is_processable_attachment(
                str(filename),
            ):
                print(
                    "Skipping unsupported attachment: "
                    f"{filename}",
                )
                continue

            attachment_response = (
                self.service.users()
                .messages()
                .attachments()
                .get(
                    userId="me",
                    messageId=message_id,
                    id=str(
                        attachment_id,
                    ),
                )
                .execute()
            )

            attachment_data = (
                attachment_response.get(
                    "data",
                )
            )

            if not attachment_data:
                continue

            file_path = (
                message_dir
                / str(filename)
            )

            file_path.write_bytes(
                self._decode_base64url_bytes(
                    str(
                        attachment_data,
                    ),
                ),
            )

            downloaded_attachments.append(
                GmailAttachmentSchema(
                    filename=str(
                        filename,
                    ),
                    file_path=str(
                        file_path,
                    ),
                ),
            )

        return downloaded_attachments

    def _iter_parts(
        self,
        payload: dict[
            str,
            Any,
        ],
    ) -> list[
        dict[
            str,
            Any,
        ]
    ]:
        parts: list[
            dict[
                str,
                Any,
            ]
        ] = []

        if payload.get(
            "parts",
        ):
            for part in payload[
                "parts"
            ]:
                parts.extend(
                    self._iter_parts(
                        part,
                    ),
                )
        else:
            parts.append(
                payload,
            )

        return parts

    @staticmethod
    def _decode_base64url(
        data: str,
    ) -> str:
        padded_data = (
            data
            + "="
            * (-len(data) % 4)
        )

        return base64.urlsafe_b64decode(
            padded_data,
        ).decode(
            "utf-8",
            errors="replace",
        )

    @staticmethod
    def _decode_base64url_bytes(
        data: str,
    ) -> bytes:
        padded_data = (
            data
            + "="
            * (-len(data) % 4)
        )

        return base64.urlsafe_b64decode(
            padded_data,
        )
