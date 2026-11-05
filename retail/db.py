"""DuckDB session over the cleaned transaction lines. The analysis SQL lives in sql/*.sql."""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from . import config


def sql_text(name: str) -> str:
    return (config.SQL_DIR / name).read_text(encoding="utf-8")


def connect(parquet: Path | None = None, raw: pd.DataFrame | None = None) -> duckdb.DuckDBPyConnection:
    """In-memory database with `raw_lines` (from Parquet, or a DataFrame in tests) and the cleaned `lines` table."""
    con = duckdb.connect()
    if raw is not None:
        con.register("raw_input", raw)
        con.execute("CREATE TABLE raw_lines AS SELECT * FROM raw_input")
        con.unregister("raw_input")
    else:
        if parquet is None:
            from .data import ensure_data

            parquet = ensure_data()
        con.read_parquet(str(parquet)).to_table("raw_lines")
    run(con, "01_clean.sql", price_error_factor=config.PRICE_ERROR_FACTOR)
    return con


def run(con: duckdb.DuckDBPyConnection, name: str, **params) -> None:
    con.execute(sql_text(name), params or None)


def query(con: duckdb.DuckDBPyConnection, name: str, **params) -> pd.DataFrame:
    return con.execute(sql_text(name), params or None).df()
