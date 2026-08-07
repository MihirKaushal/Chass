from __future__ import annotations

import base64
import binascii
import json
import os
from threading import Lock

import firebase_admin
from firebase_admin import credentials, firestore
from google.auth.credentials import AnonymousCredentials
from google.cloud.firestore_v1.client import Client

from backend.config import get_settings

_client: Client | None = None
_client_lock = Lock()


def _service_account_credential(encoded_credentials: str):
    try:
        decoded = base64.b64decode(encoded_credentials, validate=True).decode("utf-8")
        service_account = json.loads(decoded)
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("FIREBASE_CREDENTIALS_BASE64 is not valid base64 JSON") from error

    if not isinstance(service_account, dict):
        raise RuntimeError("Firebase credentials must decode to a service account object")
    return credentials.Certificate(service_account)


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

        options = {"projectId": settings.firebase_project_id}

        try:
            app = firebase_admin.get_app()
        except ValueError:
            credential = (
                _service_account_credential(settings.firebase_credentials_base64)
                if settings.firebase_credentials_base64
                else None
            )
            app = firebase_admin.initialize_app(credential, options)

        _client = firestore.client(app=app)
        return _client
