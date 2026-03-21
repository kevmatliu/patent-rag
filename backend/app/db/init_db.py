from __future__ import annotations

from sqlalchemy import text

from app.db.session import create_db_and_tables, engine


def init_db() -> None:
    create_db_and_tables()
    with engine.begin() as connection:
        columns = connection.execute(text("PRAGMA table_info(compoundimage)")).fetchall()
        column_names = {column[1] for column in columns}
        if "page_number" not in column_names:
            connection.execute(text("ALTER TABLE compoundimage ADD COLUMN page_number INTEGER"))

        job_columns = connection.execute(text("PRAGMA table_info(jobrun)")).fetchall()
        job_column_names = {column[1] for column in job_columns}
        if "cancel_requested" not in job_column_names:
            connection.execute(text("ALTER TABLE jobrun ADD COLUMN cancel_requested BOOLEAN DEFAULT 0"))
