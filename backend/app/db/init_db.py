from __future__ import annotations

from sqlalchemy import text

from app.db.migrations.normalize_core_candidates import upgrade as upgrade_core_candidate_normalization
from app.db.session import create_db_and_tables, engine


def _ensure_column(connection, table_name: str, column_name: str, ddl: str) -> None:
    columns = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    column_names = {column[1] for column in columns}
    if column_name not in column_names:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {ddl}"))


def _drop_column(connection, table_name: str, column_name: str) -> None:
    columns = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    column_names = {column[1] for column in columns}
    if column_name in column_names:
        connection.execute(text(f"ALTER TABLE {table_name} DROP COLUMN {column_name}"))


def init_db() -> None:
    create_db_and_tables()
    with engine.begin() as connection:
        _ensure_column(connection, "compoundimage", "page_number", "page_number INTEGER")
        _ensure_column(connection, "compoundimage", "canonical_smiles", "canonical_smiles TEXT")
        _ensure_column(connection, "compoundimage", "is_compound", "is_compound BOOLEAN")
        _ensure_column(
            connection,
            "compoundimage",
            "validation_status",
            "validation_status TEXT DEFAULT 'UNPROCESSED'",
        )
        _ensure_column(connection, "compoundimage", "validation_error", "validation_error TEXT")
        _ensure_column(
            connection,
            "compoundimage",
            "is_duplicate_within_patent",
            "is_duplicate_within_patent BOOLEAN DEFAULT 0",
        )
        _ensure_column(connection, "compoundimage", "duplicate_of_compound_id", "duplicate_of_compound_id INTEGER")
        _ensure_column(
            connection,
            "compoundimage",
            "kept_for_series_analysis",
            "kept_for_series_analysis BOOLEAN DEFAULT 0",
        )
        _drop_column(connection, "compoundimage", "core_match_status")
        _ensure_column(connection, "compoundimage", "pipeline_version", "pipeline_version TEXT")

        _ensure_column(connection, "jobrun", "cancel_requested", "cancel_requested BOOLEAN DEFAULT 0")

        # SQLAlchemy stores enum member names for these SQLModel enum fields, so
        # older lowercase raw TEXT values from startup migrations must be
        # normalized before ORM reads them back.
        connection.execute(
            text(
                """
                UPDATE compoundimage
                SET validation_status = CASE validation_status
                    WHEN 'unprocessed' THEN 'UNPROCESSED'
                    WHEN 'valid' THEN 'VALID'
                    WHEN 'parse_failed' THEN 'PARSE_FAILED'
                    WHEN 'sanitize_failed' THEN 'SANITIZE_FAILED'
                    WHEN 'standardize_failed' THEN 'STANDARDIZE_FAILED'
                    ELSE validation_status
                END
                """
            )
        )
        upgrade_core_candidate_normalization(connection)
        _drop_column(connection, "compoundimage", "murcko_scaffold_smiles")
        _drop_column(connection, "compoundimage", "reduced_core")
        _drop_column(connection, "compoundimage", "core_smiles")
        _drop_column(connection, "compoundimage", "core_smarts")
