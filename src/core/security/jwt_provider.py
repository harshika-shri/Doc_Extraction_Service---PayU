from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt
from jwt import PyJWTError

from src.config.settings import settings

if not hasattr(jwt, "decode"):
    raise RuntimeError(
        "PyJWT is required for token validation. "
        "Remove the conflicting 'jwt' package and install 'pyjwt'.",
    )


class JWTProvider:
    def create_access_token(
        self,
        user_id: str,
        role: str,
    ) -> str:
        payload = {
            "sub": user_id,
            "role": role,
            "token_type": "access",
            "exp": datetime.now(UTC)
            + timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
            ),
        }

        return str(
            jwt.encode(
                payload,
                settings.JWT_SECRET_KEY,
                algorithm=settings.JWT_ALGORITHM,
            ),
        )

    def create_refresh_token(
        self,
        user_id: str,
        role: str,
    ) -> tuple[str, str, datetime]:
        jti = str(uuid4())

        expires_at = datetime.now(UTC) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS,
        )

        payload = {
            "sub": user_id,
            "role": role,
            "token_type": "refresh",
            "jti": jti,
            "exp": expires_at,
        }

        token = str(
            jwt.encode(
                payload,
                settings.JWT_SECRET_KEY,
                algorithm=settings.JWT_ALGORITHM,
            ),
        )

        return (
            token,
            jti,
            expires_at,
        )

    def decode_token(
        self,
        token: str,
    ) -> dict[str, Any]:
        try:
            return jwt.decode(
                token.strip(),
                settings.JWT_SECRET_KEY,
                algorithms=[
                    settings.JWT_ALGORITHM,
                ],
            )
        except PyJWTError as err:
            raise ValueError("Invalid or expired token") from err


jwt_provider = JWTProvider()
