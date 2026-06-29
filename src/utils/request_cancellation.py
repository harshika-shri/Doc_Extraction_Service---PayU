from __future__ import annotations

from starlette.requests import Request

from src.core.exceptions.client_cancelled_exc import (
    ClientCancelledError,
)


async def ensure_client_connected(
    request: Request | None,
) -> None:
    if request is not None and await request.is_disconnected():
        raise ClientCancelledError()
