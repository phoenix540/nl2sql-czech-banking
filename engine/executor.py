"""Exécution SQL en lecture seule, avec timeout et limite de lignes."""
from __future__ import annotations

import os
import warnings
from dataclasses import dataclass
from decimal import Decimal

import pandas as pd
from sqlalchemy import create_engine, text

from engine import settings
from etl.config import db_url


@dataclass
class ExecResult:
    df: pd.DataFrame | None = None
    error: str | None = None
    truncated: bool = False


def make_engine():
    """Utilisateur lecture seule si disponible, sinon admin + transaction READ ONLY."""
    if os.getenv("RO_PASSWORD") and os.getenv("USE_READONLY_USER", "true").lower() == "true":
        try:
            eng = create_engine(db_url(read_only=True))
            with eng.connect() as c:
                c.execute(text("SELECT 1"))
            return eng, "utilisateur PostgreSQL lecture seule"
        except Exception as exc:  # noqa: BLE001
            warnings.warn(f"Utilisateur lecture seule indisponible ({type(exc).__name__}) : "
                          "repli sur transaction READ ONLY.")
    return create_engine(db_url()), "transaction READ ONLY (utilisateur admin)"


def run_query(engine, sql: str) -> ExecResult:
    raw = engine.raw_connection()  # DBAPI brut : '%' dans le SQL (LIKE 'a%') sans souci
    try:
        cur = raw.cursor()
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute(f"SET LOCAL statement_timeout = {settings.statement_timeout_s() * 1000}")
        cur.execute(sql)
        limit = settings.max_rows()
        rows = cur.fetchmany(limit + 1)
        cols = [d[0] for d in cur.description]
        df = pd.DataFrame(rows[:limit], columns=cols)
        for c in df.columns:
            if df[c].map(lambda v: isinstance(v, Decimal)).any():
                df[c] = df[c].astype(float)
        return ExecResult(df=df, truncated=len(rows) > limit)
    except Exception as exc:  # noqa: BLE001
        msg = getattr(exc, "pgerror", None) or str(exc)
        return ExecResult(error=msg.strip().splitlines()[0] if msg.strip() else type(exc).__name__)
    finally:
        try:
            raw.rollback()
        finally:
            raw.close()
