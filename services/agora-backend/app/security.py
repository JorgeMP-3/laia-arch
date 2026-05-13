from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from typing import Any


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
    return f"$pbkdf2${salt.hex()}${dk.hex()}"


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed.startswith("$pbkdf2$"):
        return False
    _, _, salt_hex, dk_hex = hashed.split("$", 3)
    salt = bytes.fromhex(salt_hex)
    expected = bytes.fromhex(dk_hex)
    actual = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt, 600_000)
    return hmac.compare_digest(actual, expected)


def _b64_encode(data: bytes) -> str:
    return urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64_decode(data: str) -> bytes:
    padding = 4 - len(data) % 4
    if padding != 4:
        data += "=" * padding
    return urlsafe_b64decode(data)


def create_token(payload: dict[str, Any], secret: str, expire_seconds: int = 1800) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload.setdefault("iat", now)
    payload["exp"] = now + expire_seconds
    payload["jti"] = secrets.token_hex(8)

    header_b64 = _b64_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}"

    sig = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    sig_b64 = _b64_encode(sig)

    return f"{signing_input}.{sig_b64}"


def verify_token(token: str, secret: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("invalid token format")

    signing_input = f"{parts[0]}.{parts[1]}"
    expected_sig = _b64_decode(parts[2])
    actual_sig = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()

    if not hmac.compare_digest(actual_sig, expected_sig):
        raise ValueError("invalid signature")

    payload = json.loads(_b64_decode(parts[1]).decode())
    if payload.get("exp", 0) < int(time.time()):
        raise ValueError("token expired")

    return payload


def create_access_token(user_id: str, role: str, secret: str) -> str:
    return create_token({"sub": user_id, "role": role}, secret, expire_seconds=1800)


def create_refresh_token(user_id: str, secret: str) -> str:
    return create_token({"sub": user_id, "type": "refresh"}, secret, expire_seconds=604800)


def _login_window_key(ip: str) -> str:
    window = int(time.time() / 60)
    return f"login:{ip}:{window}"


def should_rate_limit(ip: str, max_per_window: int = 10) -> bool:
    key = _login_window_key(ip)
    current = _rate_store.get(key, 0)
    _rate_store[key] = current + 1
    if len(_rate_store) > 1000:
        oldest = sorted(_rate_store.keys(), key=lambda k: int(k.split(":")[-1]) if k.split(":")[-1].isdigit() else 0)
        for k in oldest[:200]:
            _rate_store.pop(k, None)
    return current >= max_per_window


_rate_store: dict[str, int] = {}
