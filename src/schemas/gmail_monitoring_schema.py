from pydantic import BaseModel


class StartMonitoringRequest(
    BaseModel,
):
    email_address: str


class StopMonitoringRequest(
    BaseModel,
):
    email_address: str