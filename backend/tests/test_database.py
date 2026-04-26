from sqlalchemy import create_engine, inspect, text

from app.core import database as database_module
from app.core.config import Settings


def test_sqlite_compatibility_adds_missing_run_columns(tmp_path):
    db_path = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE run (
                    id VARCHAR NOT NULL PRIMARY KEY,
                    hypothesis VARCHAR NOT NULL,
                    preset_id VARCHAR,
                    status VARCHAR NOT NULL,
                    parsed_hypothesis_json VARCHAR,
                    literature_qc_json VARCHAR,
                    plan_json VARCHAR,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
                """
            )
        )

    original_engine = database_module.engine
    original_settings = database_module.settings
    try:
        database_module.engine = engine
        database_module.settings = Settings(database_url=f"sqlite:///{db_path}")
        database_module.ensure_sqlite_compatibility()
    finally:
        database_module.engine = original_engine
        database_module.settings = original_settings

    columns = {column["name"] for column in inspect(engine).get_columns("run")}
    assert {"review_state", "used_seed_data", "quality_summary_json"} <= columns
