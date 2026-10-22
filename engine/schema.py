"""Lecture automatique du schéma PostgreSQL -> texte pour le prompt.

Indépendant du domaine : lit tables/vues, types, commentaires (COMMENT ON) et,
pour les colonnes texte à faible cardinalité, la liste des valeurs possibles
(le LLM écrit ainsi 'Grand compte' et non 'grand_compte').
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import text

_CATALOG_SQL = text("""
SELECT c.relname, c.relkind, obj_description(c.oid, 'pg_class') AS rel_comment,
       a.attname, format_type(a.atttypid, a.atttypmod) AS typ,
       col_description(c.oid, a.attnum) AS col_comment
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_attribute a ON a.attrelid = c.oid
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'v')
  AND a.attnum > 0 AND NOT a.attisdropped
ORDER BY c.relname, a.attnum
""")


@dataclass
class Column:
    name: str
    type: str
    comment: str | None = None
    values: list[str] = field(default_factory=list)


@dataclass
class Relation:
    name: str
    kind: str
    comment: str | None
    columns: list[Column] = field(default_factory=list)


def _short_type(t: str) -> str:
    t = t.lower()
    if t.startswith("numeric"):
        return "numeric"
    if t.startswith("character") or t == "text":
        return "text"
    return t


def introspect(engine, prefix: str = "v_", max_values: int = 20):
    """Retourne (relations exposées au LLM, noms des relations interdites)."""
    rels: dict[str, Relation] = {}
    with engine.connect() as conn:
        for name, kind, rcom, col, typ, ccom in conn.execute(_CATALOG_SQL).fetchall():
            r = rels.setdefault(name, Relation(name, kind, rcom))
            r.columns.append(Column(col, _short_type(typ), ccom))

        exposed = {n: r for n, r in rels.items() if n.startswith(prefix)}
        if not exposed:  # pas de vues : on expose les tables métier
            exposed = {n: r for n, r in rels.items() if r.kind == "r" and not n.startswith("etl_")}
        blocked = set(rels) - set(exposed)

        for r in exposed.values():
            for c in r.columns:
                if c.type != "text":
                    continue
                rows = conn.execute(text(
                    f'SELECT DISTINCT "{c.name}" FROM "{r.name}" '
                    f'WHERE "{c.name}" IS NOT NULL ORDER BY 1 LIMIT {max_values + 1}')).fetchall()
                if len(rows) <= max_values:
                    c.values = [str(x[0]) for x in rows]
    return list(exposed.values()), blocked


def render(relations: list[Relation]) -> str:
    lines = []
    for r in relations:
        lines.append(f"{'VUE' if r.kind == 'v' else 'TABLE'} {r.name}" + (f" : {r.comment}" if r.comment else ""))
        for c in r.columns:
            extra = f" - {c.comment}" if c.comment else ""
            vals = f" | valeurs possibles : {', '.join(c.values)}" if c.values else ""
            lines.append(f"  - {c.name} ({c.type}){extra}{vals}")
        lines.append("")
    return "\n".join(lines).strip()
