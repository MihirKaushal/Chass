from __future__ import annotations

import sqlite3
import os
from pathlib import Path

from backend.models import GameState

DATABASE_PATH = Path(__file__).resolve().parent / "chass.db"
DEFAULT_DATABASE_URL = f"sqlite:///{DATABASE_PATH}"


def _connect() -> sqlite3.Connection:
    database_url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

    if database_url.startswith("sqlite:///"):
        sqlite_path = database_url.removeprefix("sqlite:///")
    elif database_url.startswith("postgresql://") or database_url.startswith("postgres://"):
        raise RuntimeError(
            "PostgreSQL/Supabase URL detected. Configure a Postgres adapter layer to use this URL, "
            "or run locally with a sqlite DATABASE_URL."
        )
    else:
        sqlite_path = str(DATABASE_PATH)

    connection = sqlite3.connect(sqlite_path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS games (
                id TEXT PRIMARY KEY,
                state_json TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.commit()


def save_game(game_state: GameState) -> None:
    payload = game_state.model_dump_json()
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO games (id, state_json, created_at, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                state_json = excluded.state_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (game_state.id, payload),
        )
        connection.commit()


def get_game(game_id: str) -> GameState | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT state_json FROM games WHERE id = ?",
            (game_id,),
        ).fetchone()

    if row is None:
        return None
    return GameState.model_validate_json(row["state_json"])
