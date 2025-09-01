from __future__ import annotations

import structlog
from sqlalchemy.engine import Engine

log = structlog.get_logger()


def _table_columns(engine: Engine, table: str) -> set[str]:
    """
    Return the set of column names for `table` (SQLite).
    If the table doesn't exist, returns an empty set.
    """
    with engine.connect() as conn:
        # PRAGMA returns rows like: (cid, name, type, notnull, dflt_value, pk)
        res = conn.exec_driver_sql(f"PRAGMA table_info('{table}')")
        cols = {row[1] for row in res.fetchall()}
    return cols


def _add_column_sqlite(engine: Engine, table: str, coldef_sql: str) -> None:
    """
    Add a column to a SQLite table (idempotent if you check first).
    `coldef_sql` example: "external_task_id VARCHAR(64)"
    """
    ddl = f"ALTER TABLE {table} ADD COLUMN {coldef_sql}"
    with engine.begin() as conn:
        conn.exec_driver_sql(ddl)
    log.info("db_column_added", table=table, column=coldef_sql)


def run_startup_migrations(engine: Engine) -> None:
    """
    Lightweight, idempotent migrations for SQLite (dev/demo):
      - Adds missing columns to `leads`:
          * external_task_id VARCHAR(64)
          * external_subtask_ids TEXT
    Safe to run on every startup. No destructive changes.
    """
    backend = engine.url.get_backend_name()
    if backend != "sqlite":
        # For this challenge we only implement SQLite path.
        log.info("db_migration_skipped", reason="non_sqlite_backend", backend=backend)
        return

    try:
        cols = _table_columns(engine, "leads")
        if not cols:
            # Table not found (perhaps models not imported yet)
            log.info("db_migration_skipped", reason="leads_table_missing")
            return

        if "external_task_id" not in cols:
            _add_column_sqlite(engine, "leads", "external_task_id VARCHAR(64)")

        if "external_subtask_ids" not in cols:
            _add_column_sqlite(engine, "leads", "external_subtask_ids TEXT")

        log.info("db_migration_done", table="leads")

    except Exception as e:
        # Don't crash the app on migration issues in dev; just log.
        log.exception("db_migration_error", error=str(e))
