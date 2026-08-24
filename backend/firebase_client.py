from __future__ import annotations

import base64
import binascii
import json
import logging
import os
from threading import Lock

import firebase_admin
from firebase_admin import credentials, firestore
from google.auth.credentials import AnonymousCredentials
from google.cloud.firestore_v1.client import Client

from backend.config import get_settings

logger = logging.getLogger(__name__)

_client: Client | None = None
_client_lock = Lock()
_CREDENTIAL_PREFIX = "FIREBASE_CREDENTIALS_BASE64="
_REQUIRED_SERVICE_ACCOUNT_FIELDS = {
    "client_email",
    "private_key",
    "project_id",
    "token_uri",
}


def _normalize_credential_value(value: str) -> str:
    normalized = value.strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {
        "'",
        '"',
    }:
        normalized = normalized[1:-1].strip()

    if normalized.startswith(_CREDENTIAL_PREFIX):
        normalized = normalized.removeprefix(_CREDENTIAL_PREFIX).strip()
        if (
            len(normalized) >= 2
            and normalized[0] == normalized[-1]
            and normalized[0] in {"'", '"'}
        ):
            normalized = normalized[1:-1].strip()

    return normalized


def _decode_service_account(encoded_credentials: str) -> dict:
    normalized = _normalize_credential_value(encoded_credentials)

    try:
        if normalized.startswith("{"):
            decoded = normalized
        else:
            compact = "".join(normalized.split())
            padded = compact + "=" * (-len(compact) % 4)
            decoded = base64.b64decode(padded, validate=True).decode("utf-8")
        service_account = json.loads(decoded)
    except (binascii.Error, UnicodeDecodeError, ValueError) as error:
        raise RuntimeError(
            "FIREBASE_CREDENTIALS_BASE64 is not valid JSON or base64-encoded JSON"
        ) from error

    if not isinstance(service_account, dict):
        raise RuntimeError("Firebase credentials must decode to a service account object")

    missing_fields = _REQUIRED_SERVICE_ACCOUNT_FIELDS.difference(service_account)
    if service_account.get("type") != "service_account" or missing_fields:
        raise RuntimeError(
            "Firebase credentials do not contain a complete service account"
        )

    return service_account


def _service_account_credential(service_account: dict):
    return credentials.Certificate(service_account)


def _project_id_for_service_account(
    configured_project_id: str | None,
    service_account: dict | None,
) -> str:
    credential_project_id = (
        str(service_account.get("project_id", "")).strip()
        if service_account is not None
        else ""
    )
    if credential_project_id:
        if configured_project_id and configured_project_id != credential_project_id:
            logger.warning(
                "FIREBASE_PROJECT_ID does not match the service-account project_id; "
                "using the credential project"
            )
        return credential_project_id
    if configured_project_id:
        return configured_project_id
    raise RuntimeError("A Firebase project ID is required to connect to Firestore")


def reset_firestore_client() -> None:
    """Discard a failed transport so the next request creates a fresh client."""
    global _client

    with _client_lock:
        _client = None


def get_firestore_client() -> Client:
    global _client

    if _client is not None:
        return _client

    with _client_lock:
        if _client is not None:
            return _client

        settings = get_settings()

        if os.getenv("FIRESTORE_EMULATOR_HOST"):
            _client = Client(
                project=settings.firebase_project_id,
                credentials=AnonymousCredentials(),
            )
            return _client

        service_account = (
            _decode_service_account(settings.firebase_credentials_base64)
            if settings.firebase_credentials_base64
            else None
        )
        project_id = _project_id_for_service_account(
            settings.firebase_project_id,
            service_account,
        )
        options = {"projectId": project_id}

        try:
            app = firebase_admin.get_app()
        except ValueError:
            credential = (
                _service_account_credential(service_account)
                if service_account is not None
                else None
            )
            app = firebase_admin.initialize_app(credential, options)

        _client = firestore.client(app=app)
        return _client
