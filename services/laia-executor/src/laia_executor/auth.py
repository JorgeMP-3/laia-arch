"""Bearer-token authentication for the executor.

AGORA holds the same token in `agents.api_token` and sends it in every request.
The token is mounted at /etc/laia/executor-token (mode 0600) inside the container.
"""

from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, status


def require_bearer_token(expected_token: str):
    """Build a FastAPI dependency that validates the Authorization header.

    The dependency uses hmac.compare_digest to mitigate timing attacks.
    """

    async def _dep(authorization: str | None = Header(default=None)) -> None:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="missing bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        presented = authorization[len("Bearer "):].strip()
        if not hmac.compare_digest(presented, expected_token):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="invalid bearer token",
            )

    return _dep
