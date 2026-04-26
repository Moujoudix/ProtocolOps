from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import get_settings


settings = get_settings()

connect_args = {}
engine_kwargs = {}

if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    if settings.database_url != "sqlite:///:memory:":
        db_path = settings.database_url.removeprefix("sqlite:///")
        if db_path and db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    else:
        engine_kwargs["poolclass"] = StaticPool

engine = create_engine(settings.database_url, connect_args=connect_args, **engine_kwargs)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    ensure_sqlite_compatibility()


def ensure_sqlite_compatibility() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    if "run" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("run")}
    migrations = {
        "review_state": "ALTER TABLE run ADD COLUMN review_state VARCHAR NOT NULL DEFAULT 'generated'",
        "evidence_mode": "ALTER TABLE run ADD COLUMN evidence_mode VARCHAR NOT NULL DEFAULT 'seeded_demo'",
        "used_seed_data": "ALTER TABLE run ADD COLUMN used_seed_data BOOLEAN NOT NULL DEFAULT 0",
        "quality_summary_json": "ALTER TABLE run ADD COLUMN quality_summary_json VARCHAR",
    }

    pending = [statement for column, statement in migrations.items() if column not in existing_columns]
    if not pending:
        return

    with engine.begin() as connection:
        for statement in pending:
            connection.execute(text(statement))


def get_session():
    with Session(engine) as session:
        yield session
