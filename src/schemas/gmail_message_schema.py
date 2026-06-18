from pydantic import BaseModel


class GmailAttachmentSchema(
    BaseModel,
):
    filename: str
    file_path: str


class GmailMessageSchema(
    BaseModel,
):
    message_id: str
    subject: str
    body: str
    sender_email: str | None = None
    attachments: list[
        GmailAttachmentSchema
    ]
