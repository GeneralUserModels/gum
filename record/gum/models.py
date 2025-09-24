# models.py

from __future__ import annotations

import pathlib
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    text as sql_text,
)
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)
from sqlalchemy.sql import func

class Base(AsyncAttrs, DeclarativeBase):
    pass

observation_proposition = Table(
    "observation_proposition",
    Base.metadata,
    Column(
        "observation_id",
        Integer,
        ForeignKey("observations.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "proposition_id",
        Integer,
        ForeignKey("propositions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

proposition_parent = Table(
    "proposition_parent",
    Base.metadata,
    Column(
        "child_id",
        Integer,
        ForeignKey("propositions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "parent_id",
        Integer,
        ForeignKey("propositions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Observation(Base):
    __tablename__ = "observations"

    id:            Mapped[int]   = mapped_column(primary_key=True)
    observer_name: Mapped[str]   = mapped_column(String(100), nullable=False)
    content:       Mapped[str]   = mapped_column(Text,        nullable=False)
    content_type:  Mapped[str]   = mapped_column(String(50),  nullable=False)
    # New optional metadata fields for each action/observation
    app_name:      Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    browser_url:   Mapped[Optional[str]] = mapped_column(Text,        nullable=True)

    created_at:    Mapped[str]   = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at:    Mapped[str]   = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    propositions: Mapped[set["Proposition"]] = relationship(
        "Proposition",
        secondary=observation_proposition,
        back_populates="observations",
        collection_class=set,
        passive_deletes=True,
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Observation(id={self.id}, observer={self.observer_name})>"


class Proposition(Base):
    __tablename__ = "propositions"

    id:         Mapped[int]           = mapped_column(primary_key=True)
    text:       Mapped[str]           = mapped_column(Text, nullable=False)
    reasoning:  Mapped[str]           = mapped_column(Text, nullable=False)
    confidence: Mapped[Optional[int]]
    decay:      Mapped[Optional[int]]

    created_at: Mapped[str]           = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[str]           = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    revision_group: Mapped[str]       = mapped_column(String(36), nullable=False, index=True)
    version:        Mapped[int]       = mapped_column(Integer, server_default="1", nullable=False)

    parents: Mapped[set["Proposition"]] = relationship(
        "Proposition",
        secondary=proposition_parent,
        primaryjoin=id == proposition_parent.c.child_id,
        secondaryjoin=id == proposition_parent.c.parent_id,
        backref="children",
        collection_class=set,
        lazy="selectin",
    )

    observations: Mapped[set[Observation]] = relationship(
        "Observation",
        secondary=observation_proposition,
        back_populates="propositions",
        collection_class=set,
        passive_deletes=True,
        lazy="selectin",
    )

    def __repr__(self) -> str:
        preview = (self.text[:27] + "…") if len(self.text) > 30 else self.text
        return f"<Proposition(id={self.id}, text={preview})>"


FTS_TOKENIZER = "porter ascii"

def create_fts_table(conn) -> None:
    """Create FTS5 virtual table + triggers on first run."""
    exists = conn.execute(
        sql_text(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='propositions_fts'"
        )
    ).fetchone()
    if exists:
        return

    conn.execute(
        sql_text(
            f"""
            CREATE VIRTUAL TABLE propositions_fts
            USING fts5(
                text,
                reasoning,
                content='propositions',
                content_rowid='id',
                tokenize='{FTS_TOKENIZER}'
            );
        """
        )
    )
    conn.execute(
        sql_text(
            """
            CREATE TRIGGER propositions_ai
            AFTER INSERT ON propositions BEGIN
                INSERT INTO propositions_fts(rowid, text, reasoning)
                VALUES (new.id, new.text, new.reasoning);
            END;
        """
        )
    )
    conn.execute(
        sql_text(
            """
            CREATE TRIGGER propositions_ad
            AFTER DELETE ON propositions BEGIN
                INSERT INTO propositions_fts(propositions_fts, rowid, text, reasoning)
                VALUES('delete', old.id, old.text, old.reasoning);
            END;
        """
        )
    )
    conn.execute(
        sql_text(
            """
            CREATE TRIGGER propositions_au
            AFTER UPDATE ON propositions BEGIN
                INSERT INTO propositions_fts(propositions_fts, rowid, text, reasoning)
                VALUES('delete', old.id, old.text, old.reasoning);
                INSERT INTO propositions_fts(rowid, text, reasoning)
                VALUES(new.id, new.text, new.reasoning);
            END;
        """
        )
    )
    conn.execute(
        sql_text(
            """
            INSERT INTO propositions_fts(rowid, text, reasoning)
            SELECT id, text, reasoning FROM propositions;
        """
        )
    )

async def init_db(
    db_path: str = "gum.db",
    db_directory: Optional[str] = None,
):
    """Create the SQLite file, ORM tables & FTS5 index (first run only)."""
    if db_directory:
        path = pathlib.Path(db_directory).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        db_path = str(path / db_path)

    engine: AsyncEngine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        future=True,
        connect_args={
            "timeout": 30,
            "isolation_level": None,
        },
        poolclass=None,
    )

    async with engine.begin() as conn:
        await conn.execute(sql_text("PRAGMA journal_mode=WAL"))
        await conn.execute(sql_text("PRAGMA busy_timeout=30000"))

        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(create_fts_table)
        # Ensure new columns exist when upgrading an existing DB without migrations
        def _ensure_observation_columns(sync_conn):
            info = sync_conn.execute(sql_text("PRAGMA table_info(observations)")).fetchall()
            cols = {row[1] for row in info}
            if "app_name" not in cols:
                sync_conn.execute(sql_text("ALTER TABLE observations ADD COLUMN app_name VARCHAR(100)"))
            if "browser_url" not in cols:
                sync_conn.execute(sql_text("ALTER TABLE observations ADD COLUMN browser_url TEXT"))
        await conn.run_sync(_ensure_observation_columns)

    Session = async_sessionmaker(
        engine, 
        expire_on_commit=False,
        autoflush=False
    )
    return engine, Session
