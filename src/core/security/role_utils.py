from fastapi import HTTPException, status

from src.data.models.postgres.enums import UserRole

ROLE_ALIASES: dict[str, UserRole] = {
    "admin": UserRole.ADMIN,
    "finance_associate": UserRole.FINANCE_ASSOCIATE,
    "finance_manager": UserRole.FINANCE_MANAGER,
    "ADMIN": UserRole.ADMIN,
    "FINANCE_ASSOCIATE": UserRole.FINANCE_ASSOCIATE,
    "FINANCE_MANAGER": UserRole.FINANCE_MANAGER,
}


def parse_user_role(
    role_value: str | None,
) -> UserRole:
    if not role_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Role claim missing from token",
        )

    normalized_role = (
        ROLE_ALIASES.get(role_value)
        or ROLE_ALIASES.get(
            role_value.strip().lower(),
        )
    )

    if normalized_role is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid role claim in token",
        )

    return normalized_role
