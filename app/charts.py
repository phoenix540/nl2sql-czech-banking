"""Choix automatique du graphique selon la forme du résultat (sans dépendance Streamlit)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd


@dataclass
class ChartSpec:
    kind: str          # "line" | "bar"
    x: str
    ys: list[str]


def classify(df: pd.DataFrame) -> dict[str, list[str]]:
    out = {"date": [], "num": [], "cat": []}
    for c in df.columns:
        s = df[c].dropna()
        if s.empty:
            out["cat"].append(c)
        elif isinstance(s.iloc[0], (date, datetime, pd.Timestamp)):
            out["date"].append(c)
        elif pd.api.types.is_numeric_dtype(df[c]) and not str(c).endswith("_id"):
            out["num"].append(c)
        else:
            out["cat"].append(c)
    return out


def suggest_chart(df: pd.DataFrame, force: str | None = None) -> ChartSpec | None:
    """force : None (auto) | 'line' | 'bar'. Renvoie None si aucun graphique pertinent."""
    if df is None or len(df) < 2:
        return None
    k = classify(df)
    if not k["num"]:
        return None
    ys = k["num"][:3]
    x = (k["date"] or k["cat"] or [None])[0]
    if x is None:
        return None
    if force:
        return ChartSpec(force, x, ys)
    if k["date"]:
        return ChartSpec("line", k["date"][0], ys)
    if len(k["cat"]) == 1 and len(df) <= 40:
        return ChartSpec("bar", k["cat"][0], ys)
    return None


def chart_frame(df: pd.DataFrame, spec: ChartSpec) -> pd.DataFrame:
    frame = df[[spec.x, *spec.ys]].copy()
    if frame[spec.x].map(lambda v: isinstance(v, (date, datetime, pd.Timestamp))).all():
        frame[spec.x] = pd.to_datetime(frame[spec.x])
        frame = frame.sort_values(spec.x)
    else:
        frame[spec.x] = frame[spec.x].astype(str)
    return frame.set_index(spec.x)
