from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
    inspect,
    text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from backend.config import get_settings


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class GameRow(Base):
    __tablename__ = "games"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="local")
    state_json: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class GamePlayerRow(Base):
    __tablename__ = "game_players"
    __table_args__ = (
        UniqueConstraint("game_id", "color", name="uq_game_player_color"),
        Index("ix_game_players_token_hash", "token_hash", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    game_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True
    )
    color: Mapped[str] = mapped_column(String(16), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class GameInviteRow(Base):
    __tablename__ = "game_invites"
    __table_args__ = (Index("ix_game_invites_token_hash", "token_hash", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    game_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    target_color: Mapped[str] = mapped_column(String(16), nullable=False, default="black")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MoveRow(Base):
    __tablename__ = "moves"
    __table_args__ = (
        UniqueConstraint("game_id", "game_version", name="uq_move_game_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    game_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True
    )
    game_version: Mapped[int] = mapped_column(Integer, nullable=False)
    move_number: Mapped[int] = mapped_column(Integer, nullable=False)
    player_color: Mapped[str] = mapped_column(String(16), nullable=False)
    piece_type: Mapped[str] = mapped_column(String(64), nullable=False)
    from_row: Mapped[int] = mapped_column(Integer, nullable=False)
    from_col: Mapped[int] = mapped_column(Integer, nullable=False)
    to_row: Mapped[int] = mapped_column(Integer, nullable=False)
    to_col: Mapped[int] = mapped_column(Integer, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


_engine: Engine | None = None
_engine_url: str | None = None
_session_factory: sessionmaker[Session] | None = None


def _normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def get_engine() -> Engine:
    global _engine, _engine_url, _session_factory

    database_url = _normalize_database_url(get_settings().database_url)
    if _engine is not None and _engine_url == database_url:
        return _engine

    if _engine is not None:
        _engine.dispose()

    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine_options = {
        "connect_args": connect_args,
        "pool_pre_ping": True,
    }
    if database_url.startswith("postgresql"):
        engine_options.update({"pool_size": 5, "max_overflow": 2, "pool_recycle": 300})

    _engine = create_engine(database_url, **engine_options)
    if database_url.startswith("sqlite"):
        @event.listens_for(_engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, _):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    _engine_url = database_url
    _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def _upgrade_legacy_games_table(engine: Engine) -> None:
    inspector = inspect(engine)
    if "games" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("games")}
    additions = {
        "mode": "VARCHAR(16) NOT NULL DEFAULT 'local'",
        "version": "INTEGER NOT NULL DEFAULT 1",
        "expires_at": "TIMESTAMP NULL",
    }

    with engine.begin() as connection:
        for column, definition in additions.items():
            if column not in existing:
                connection.execute(text(f"ALTER TABLE games ADD COLUMN {column} {definition}"))


def init_db() -> None:
    engine = get_engine()
    _upgrade_legacy_games_table(engine)
    Base.metadata.create_all(engine)


@contextmanager
def session_scope() -> Iterator[Session]:
    get_engine()
    if _session_factory is None:
        raise RuntimeError("Database session factory is unavailable")

    session = _session_factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_database_engine() -> None:
    """Dispose cached connections; intended for tests and process reconfiguration."""
    global _engine, _engine_url, _session_factory

    if _engine is not None:
        _engine.dispose()
    _engine = None
    _engine_url = None
    _session_factory = None
