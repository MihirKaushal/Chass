from __future__ import annotations

import base64
import json

import pytest

from backend.firebase_client import _decode_service_account

SERVICE_ACCOUNT = {
    "type": "service_account",
    "project_id": "chass-test",
    "private_key": "test-private-key",
    "client_email": "firebase-adminsdk@chass-test.iam.gserviceaccount.com",
    "token_uri": "https://oauth2.googleapis.com/token",
}


def _encoded_service_account() -> str:
    serialized = json.dumps(SERVICE_ACCOUNT).encode("utf-8")
    return base64.b64encode(serialized).decode("ascii")


@pytest.mark.parametrize(
    "credential_value",
    [
        _encoded_service_account(),
        f"  '{_encoded_service_account()}'  ",
        f"FIREBASE_CREDENTIALS_BASE64={_encoded_service_account()}",
        "\n".join(
            _encoded_service_account()[offset : offset + 40]
            for offset in range(0, len(_encoded_service_account()), 40)
        ),
        _encoded_service_account().rstrip("="),
        json.dumps(SERVICE_ACCOUNT),
    ],
)
def test_decode_service_account_accepts_safe_render_formats(credential_value):
    assert _decode_service_account(credential_value) == SERVICE_ACCOUNT


@pytest.mark.parametrize(
    "credential_value",
    [
        "not-base64",
        base64.b64encode(b"[]").decode("ascii"),
        base64.b64encode(b'{"type":"service_account"}').decode("ascii"),
    ],
)
def test_decode_service_account_rejects_invalid_credentials(credential_value):
    with pytest.raises(RuntimeError):
        _decode_service_account(credential_value)
