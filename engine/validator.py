"""Garde-fou SQL : n'autorise qu'une seule requête de lecture sur les relations exposées.

Ce n'est que la 1re couche. Les couches réelles de sécurité sont côté base :
utilisateur PostgreSQL SELECT-only, transaction READ ONLY et statement_timeout.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

FORBIDDEN = {
    "insert", "update", "delete", "drop", "alter", "create", "truncate", "grant", "revoke",
    "copy", "call", "do", "execute", "merge", "vacuum", "analyze", "reindex", "listen",
    "notify", "lock", "set", "reset", "show", "explain", "into", "prepare", "deallocate",
    "refresh", "comment", "begin", "commit", "rollback", "savepoint", "discard",
}
FORBIDDEN_PREFIXES = ("pg_", "lo_", "dblink")
FORBIDDEN_NAMES = {"information_schema", "current_setting", "set_config"}

_COMMENT = re.compile(r"--[^\n]*|/\*.*?\*/", re.S)
_STRING = re.compile(r"'(?:[^']|'')*'")
_DQUOTED = re.compile(r'"([^"]*)"')


@dataclass
class Validation:
    ok: bool
    sql: str = ""
    error: str = ""


def validate(sql: str, blocked: frozenset | set = frozenset()) -> Validation:
    if not sql or not sql.strip():
        return Validation(False, error="Requête vide.")
    s = _COMMENT.sub(" ", sql).strip()
    masked = _STRING.sub("''", s)
    masked = _DQUOTED.sub(r"\1", masked).rstrip().rstrip(";").rstrip()
    if ";" in masked:
        return Validation(False, error="Une seule requête SQL est autorisée (pas de ';' multiple).")
    tokens = re.findall(r"[a-z_][a-z0-9_]*", masked.lower())
    if not tokens or tokens[0] not in ("select", "with"):
        return Validation(False, error="Seules les requêtes SELECT (ou WITH ... SELECT) sont autorisées.")
    bad = FORBIDDEN & set(tokens)
    if bad:
        return Validation(False, error=f"Mot-clé interdit : {', '.join(sorted(bad))}.")
    for t in set(tokens):
        if t.startswith(FORBIDDEN_PREFIXES) or t in FORBIDDEN_NAMES:
            return Validation(False, error=f"Fonction ou schéma système interdit : {t}.")
    hit = set(tokens) & set(blocked)
    if hit:
        return Validation(False, error=f"Relation non autorisée : {', '.join(sorted(hit))}. "
                                       "Utilise uniquement les vues listées dans le schéma.")
    return Validation(True, sql=s.rstrip().rstrip(";").rstrip())
