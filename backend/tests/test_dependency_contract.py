from __future__ import annotations

from importlib.metadata import version
from pathlib import Path

from google.auth.credentials import AnonymousCredentials
from google.cloud.firestore_v1.client import Client

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_firestore_client_uses_the_verified_release():
    assert version("google-cloud-firestore") == "2.28.1"
    assert version("google-api-core") == "2.34.0"


def test_default_firestore_database_path_remains_literal():
    client = Client(
        project="chass-dependency-check",
        credentials=AnonymousCredentials(),
    )
    assert (
        client._database_string
        == "projects/chass-dependency-check/databases/(default)"
    )


def test_render_python_matches_the_verified_local_runtime():
    assert (PROJECT_ROOT / ".python-version").read_text().strip() == "3.13.12"
