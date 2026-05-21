from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Header, HTTPException

from .config import settings
from .models import Role, User
from .security import create_access_token, create_refresh_token, hash_password, verify_password
from .storage import store


def public_user(user: User) -> User:
    data = user.model_dump()
    data["password"] = None
    return User.model_validate(data)


def authenticate(username: str, password: str) -> User | None:
    for user in store.users():
        if user.username != username:
            continue
        pw = user.password or ""
        if pw.startswith("$pbkdf2$"):
            if verify_password(password, pw):
                return user
        elif pw == password:
            user.password = hash_password(password)
            store.save_user(user)
            return user
    return None


def issue_tokens(user: User) -> dict[str, str]:
    secret = settings.jwt_secret
    return {
        "access_token": create_access_token(user.id, user.role, secret),
        "refresh_token": create_refresh_token(user.id, secret),
        "token_type": "bearer",
    }


def current_user(authorization: str | None = Header(default=None)) -> User:
    from .security import verify_token

    if not authorization:
        raise HTTPException(status_code=401, detail="missing authorization")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="invalid authorization")

    try:
        payload = verify_token(token, settings.jwt_secret)
    except ValueError as exc:
        user = store.user_by_token(token)
        if user:
            return user
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="invalid token payload")

    user = store.user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="user not found")

    # Revocation cut-off (POST /api/logout). Tokens issued before this
    # instant are rejected even if their JWT exp hasn't passed yet.
    cutoff = store.tokens_valid_since(user_id)
    if cutoff and int(payload.get("iat", 0)) <= cutoff:
        raise HTTPException(status_code=401, detail="token revoked")
    return user


def require_roles(*roles: Role) -> Callable[[User], User]:
    allowed = set(roles)

    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=403, detail="insufficient role")
        return user

    return dependency


def can_access_user_scope(actor: User, user_id: str | None) -> bool:
    if actor.role == "agora_admin":
        return True
    if actor.role == "employee":
        return user_id in {None, actor.id}
    if actor.role == "agent":
        return user_id in {None, actor.id}
    return False
