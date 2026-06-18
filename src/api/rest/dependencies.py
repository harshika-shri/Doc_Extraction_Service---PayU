from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security.jwt_provider import jwt_provider
from src.core.security.role_utils import parse_user_role
from src.data.clients.postgres_client import (
    get_session_factory,
)
from src.data.models.postgres.enums import UserRole
from src.data.models.postgres.users import User
from src.data.repositories.user_repo import UserRepository

security = HTTPBearer(
    auto_error=False,
)


async def get_db_session(
) -> AsyncGenerator[
    AsyncSession,
    None,
]:
    session_factory = (
        get_session_factory()
    )

    async with session_factory() as session:
        try:
            yield session

            await session.commit()

        except Exception:
            await session.rollback()
            raise


async def get_access_token_payload(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        security,
    ),
) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token",
        )

    token = credentials.credentials

    try:
        payload = jwt_provider.decode_token(
            token,
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from err

    if payload.get("token_type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    parse_user_role(
        payload.get("role"),
    )

    return payload


async def get_current_user(
    payload: dict[str, Any] = Depends(
        get_access_token_payload,
    ),
    session: AsyncSession = Depends(
        get_db_session,
    ),
) -> User:
    repo = UserRepository(session)

    user = await repo.get_user_by_id(
        UUID(payload["sub"]),
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )

    token_role = parse_user_role(
        payload.get("role"),
    )

    if user.role.value != token_role.value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token role does not match user record",
        )

    return user


def require_roles(
    *allowed_roles: UserRole,
) -> Callable[..., Awaitable[User]]:
    async def role_checker(
        payload: dict[str, Any] = Depends(
            get_access_token_payload,
        ),
        current_user: User = Depends(
            get_current_user,
        ),
    ) -> User:
        token_role = parse_user_role(
            payload.get("role"),
        )

        if token_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )

        return current_user

    return role_checker
