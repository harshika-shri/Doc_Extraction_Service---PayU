from pydantic import BaseModel


class StartMonitoringRequest(
    BaseModel,
):
    email_address: str


class StopMonitoringRequest(
    BaseModel,
):
    email_address: str


class MonitoringStatusResponse(BaseModel):
    email_address: str
    is_monitoring: bool
    last_processed_history_id: int | None = None