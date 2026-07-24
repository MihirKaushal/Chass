from __future__ import annotations

import hashlib
import hmac
import secrets

from backend.config import get_settings


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    secret = get_settings().token_secret.encode("utf-8")
    return hmac.new(secret, token.encode("utf-8"), hashlib.sha256).hexdigest()
