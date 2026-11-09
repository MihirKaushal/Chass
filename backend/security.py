from __future__ import annotations

import hashlib
import hmac
import secrets

from backend.config import get_settings

INVITE_CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
INVITE_CODE_LENGTH = 8


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def generate_invite_code() -> str:
    return "".join(secrets.choice(INVITE_CODE_ALPHABET) for _ in range(INVITE_CODE_LENGTH))


def normalize_invite_credential(value: str) -> str:
    stripped = value.strip()
    compact = stripped.replace("-", "").replace(" ", "")
    if len(compact) == INVITE_CODE_LENGTH and compact.isalnum():
        return compact.upper()
    return stripped


def hash_token(token: str) -> str:
    secret = get_settings().token_secret.encode("utf-8")
    return hmac.new(secret, token.encode("utf-8"), hashlib.sha256).hexdigest()
