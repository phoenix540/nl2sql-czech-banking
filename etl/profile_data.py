"""Profilage automatique de tous les CSV de data/czech/.

Détecte : doublons, valeurs manquantes, formats de date mixtes, nombres
écrits avec virgule, espaces parasites, variantes de libellés, valeurs
aberrantes et références orphelines entre tables. Indépendant du domaine.

Usage : python -m etl.profile_data
"""
from __future__ import annotations

import re

import pandas as pd

from etl.clean import norm_key
from etl.config import CZECH_DIR, REPORTS_DIR

ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
FR = re.compile(r"^\d{2}/\d{2}/\d{4}$")
DEC_COMMA = re.compile(r"^-?\d+,\d+$")


def infer_type(nn: pd.Series) -> str:
    if nn.empty:
        return "vide"
    if (nn.str.match(ISO) | nn.str.match(FR)).mean() > 0.95:
        return "date"
    if nn.str.match(r"^0\d+$").mean() > 0.95:
        return "texte (zéros en tête, à ne pas convertir)"
    num = pd.to_numeric(nn.str.replace(",", ".", regex=False), errors="coerce")
    if num.notna().mean() > 0.95:
        return "entier" if (num.dropna() % 1 == 0).all() else "décimal"
    return "texte"


def profile_table(name: str, df: pd.DataFrame) -> tuple[list[dict], list[str]]:
    issues: list[str] = []
    cols: list[dict] = []
    if (d := df.duplicated().sum()):
        issues.append(f"{d} lignes entièrement dupliquées")
    key = df.columns[0]
    if key.endswith("_id") and (d := df[key].duplicated().sum()):
        issues.append(f"{d} doublons sur la clé `{key}`")

    for c in df.columns:
        s = df[c]
        nn = s.dropna().astype(str)
        typ = infer_type(nn)
        info = {"colonne": c, "type": typ, "nulls": int(s.isna().sum()),
                "distincts": int(s.nunique()), "exemples": ", ".join(nn.drop_duplicates().head(3))}
        cols.append(info)
        if info["nulls"]:
            issues.append(f"`{c}` : {info['nulls']} valeurs manquantes ({info['nulls']/len(df):.1%})")
        if (ws := int((nn != nn.str.strip()).sum())):
            issues.append(f"`{c}` : {ws} valeurs avec espaces parasites")
        if typ == "date":
            nfr, niso = int(nn.str.match(FR).sum()), int(nn.str.match(ISO).sum())
            if nfr and niso:
                issues.append(f"`{c}` : formats de date mixtes ({niso} ISO / {nfr} JJ/MM/AAAA)")
        if typ in ("décimal", "entier") and (dc := int(nn.str.match(DEC_COMMA).sum())):
            issues.append(f"`{c}` : {dc} nombres avec virgule décimale (colonne lue comme texte)")
        if typ in ("entier", "décimal") and not c.endswith("_id"):
            v = pd.to_numeric(nn.str.replace(",", ".", regex=False), errors="coerce").dropna()
            if len(v):
                p99 = v[v > 0].quantile(0.99) if (v > 0).any() else 0
                if (neg := int((v <= 0).sum())):
                    issues.append(f"`{c}` : {neg} valeurs <= 0")
                if p99 and (hi := int((v > 20 * p99).sum())):
                    issues.append(f"`{c}` : {hi} valeurs aberrantes (> 20 x P99 = {20*p99:,.0f}), max = {v.max():,.0f}")
        if typ == "texte" and 1 < s.nunique() <= 60:
            groups = nn.groupby(nn.map(norm_key)).agg(lambda x: sorted(set(x)))
            variants = groups[groups.map(len) > 1]
            if len(variants):
                ex = " ; ".join("/".join(v) for v in variants.head(3))
                issues.append(f"`{c}` : variantes d'un même libellé ({ex}...)")
    return cols, issues


def find_orphans(tables: dict[str, pd.DataFrame]) -> list[str]:
    out = []
    keys = {t: df.columns[0] for t, df in tables.items()}
    for t, df in tables.items():
        for c in df.columns[1:]:
            for parent, pk in keys.items():
                if parent != t and c == pk:
                    child = pd.to_numeric(df[c], errors="coerce").dropna()
                    ref = set(pd.to_numeric(tables[parent][pk], errors="coerce").dropna())
                    n = int((~child.isin(ref)).sum())
                    out.append(f"`{t}.{c}` -> `{parent}.{pk}` : "
                               + (f"{n} références orphelines" if n else "intégrité OK"))
    return out


def main():
    tables = {p.stem: pd.read_csv(p, sep=";", dtype=str, encoding="utf-8-sig") for p in sorted(CZECH_DIR.glob("*.csv"))}
    if not tables:
        raise SystemExit(f"Aucun CSV dans {CZECH_DIR}")
    md = ["# Rapport de profilage des données brutes\n"]
    total = 0
    for name, df in tables.items():
        cols, issues = profile_table(name, df)
        total += len(issues)
        md += [f"## {name} ({len(df):,} lignes, {len(df.columns)} colonnes)\n",
               "| Colonne | Type inféré | Nulls | Distincts | Exemples |", "|---|---|---|---|---|"]
        md += [f"| {c['colonne']} | {c['type']} | {c['nulls']} | {c['distincts']} | {c['exemples']} |" for c in cols]
        md += ["", "**Problèmes détectés :**\n"] + ([f"- {i}" for i in issues] or ["- aucun"]) + [""]
    orph = find_orphans(tables)
    md += ["## Intégrité référentielle\n"] + [f"- {o}" for o in orph]
    REPORTS_DIR.mkdir(exist_ok=True)
    (REPORTS_DIR / "profiling_report.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))
    print(f"\n>>> {total} problèmes de qualité détectés. Rapport : reports/profiling_report.md")


if __name__ == "__main__":
    main()
