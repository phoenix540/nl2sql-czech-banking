"""Explication en langage naturel d'un résultat (tableau ou graphique).

Les statistiques sont calculées en Python, puis le LLM les reformule : il ne fait
aucun calcul lui-même, ce qui limite les chiffres inventés. La réponse est
structurée (titre + observations typées) et accompagnée de chiffres clés.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime

import pandas as pd

from engine.llm import _THINK

MAX_SAMPLE_ROWS = 15

SYSTEM_PROMPT = """Tu es un analyste de données bancaires. On te donne une question \
posée en français, la requête SQL exécutée et un résumé statistique du résultat.
Explique le résultat à un utilisateur non technique, en français simple.

Réponds UNIQUEMENT avec un objet JSON de la forme :
{"titre": "...", "points": [{"type": "...", "texte": "..."}]}
- "titre" : une seule phrase courte (20 mots maximum) qui répond directement à la question ;
- "points" : 2 à 4 observations courtes (une phrase chacune), sans répéter le titre ;
- "type" vaut "max" (valeur la plus forte), "min" (valeur la plus faible), \
"tendance" (évolution dans le temps), "repartition" (concentration, écarts, parts), \
"graphique" (comment lire le graphique affiché) ou "info" (autre remarque) ;
- utilise UNIQUEMENT les chiffres fournis, n'invente rien et ne recalcule rien ;
- les statistiques portent sur toutes les lignes ; l'échantillon de lignes ne sert \
qu'à comprendre le contenu : ne le commente pas, l'utilisateur voit toutes les lignes ;
- ne qualifie une évolution de « continue » ou « régulière » que si le résumé le dit ;
- si le résultat est tronqué, ajoute un point "info" qui le signale ;
- pas de SQL, pas de jargon technique, pas de noms de colonnes avec des underscores ;
- les montants sont en couronnes tchèques (CZK) lorsqu'il s'agit de montants."""

POINT_TYPES = ("max", "min", "tendance", "repartition", "graphique", "info")


@dataclass
class Highlight:
    label: str
    value: str
    delta: str | None = None
    help: str | None = None


@dataclass
class Explanation:
    title: str
    points: list[tuple[str, str]] = field(default_factory=list)  # (type, texte)
    highlights: list[Highlight] = field(default_factory=list)

    def as_text(self) -> str:
        return "\n".join([self.title, *(f"- {t}" for _, t in self.points)])


def _fmt(v) -> str:
    if isinstance(v, (pd.Timestamp, datetime)):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, float):
        return f"{v:,.0f}".replace(",", " ") if v.is_integer() else f"{v:,.2f}".replace(",", " ")
    if isinstance(v, int):
        return f"{v:,}".replace(",", " ")
    if hasattr(v, "item"):  # scalaires numpy
        return _fmt(v.item())
    return str(v)


def pretty(col) -> str:
    """'nombre_prets' -> 'Nombre prets'."""
    text = str(col).replace("_", " ").strip()
    return text[:1].upper() + text[1:]


def _is_date_col(s: pd.Series) -> bool:
    s = s.dropna()
    return not s.empty and isinstance(s.iloc[0], (date, datetime, pd.Timestamp))


def _numeric_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns
            if pd.api.types.is_numeric_dtype(df[c]) and not pd.api.types.is_bool_dtype(df[c])
            and not str(c).endswith("_id")]


def _label_col(df: pd.DataFrame, nums: list[str], label_col: str | None) -> str | None:
    if label_col is not None:
        return label_col
    others = [c for c in df.columns if c not in nums]
    return others[0] if others else None


def summarize(df: pd.DataFrame, label_col: str | None = None) -> str:
    """Résumé compact et déterministe du DataFrame, destiné au prompt."""
    lines = [f"{len(df)} ligne(s), colonnes : {', '.join(map(str, df.columns))}"]
    if df.empty:
        return lines[0]
    nums = _numeric_cols(df)
    label_col = _label_col(df, nums, label_col)

    for c in nums:
        s = pd.to_numeric(df[c], errors="coerce").dropna()
        if s.empty:
            continue
        parts = [f"total {_fmt(s.sum())}", f"moyenne {_fmt(float(s.mean()))}"]
        for name, idx in (("max", s.idxmax()), ("min", s.idxmin())):
            who = f" ({_fmt(df.at[idx, label_col])})" if label_col else ""
            parts.append(f"{name} {_fmt(s[idx])}{who}")
        if (label_col and not _is_date_col(df[label_col]) and len(s) > 3
                and s.sum() > 0 and (s >= 0).all()):
            top = s.nlargest(3)
            names = ", ".join(_fmt(df.at[i, label_col]) for i in top.index)
            parts.append(f"les 3 plus grandes valeurs ({names}) représentent "
                         f"ensemble {top.sum() / s.sum() * 100:.0f} % du total")
        lines.append(f"- {c} : " + ", ".join(parts))

    if label_col and _is_date_col(df[label_col]) and nums:
        ordered = df.sort_values(label_col)
        first, last = ordered.iloc[0], ordered.iloc[-1]
        for c in nums[:3]:
            lines.append(f"- évolution de {c} : {_fmt(first[c])} au {_fmt(first[label_col])} "
                         f"-> {_fmt(last[c])} au {_fmt(last[label_col])}")
            s = pd.to_numeric(ordered[c], errors="coerce").dropna()
            diffs = s.diff().dropna()
            ups, downs = int((diffs > 0).sum()), int((diffs < 0).sum())
            shape = ("hausse continue" if downs == 0 else "baisse continue" if ups == 0
                     else f"évolution irrégulière : {ups} hausses et {downs} baisses d'une période à l'autre")
            lines.append(f"  {shape}")
            peak = s.idxmax()
            if downs and s[peak] > s.iloc[-1]:
                lines.append(f"  après le pic du {_fmt(ordered.at[peak, label_col])} "
                             f"({_fmt(s[peak])}), la valeur redescend à {_fmt(s.iloc[-1])}")

    sample = df.head(MAX_SAMPLE_ROWS)
    head = "Lignes" if len(df) <= MAX_SAMPLE_ROWS else f"Premières {MAX_SAMPLE_ROWS} lignes (échantillon)"
    rows = [" | ".join(_fmt(v) for v in r) for r in sample.itertuples(index=False)]
    lines.append(f"{head} :\n" + " | ".join(map(str, df.columns)) + "\n" + "\n".join(rows))
    return "\n".join(lines)


def highlights(df: pd.DataFrame, label_col: str | None = None) -> list[Highlight]:
    """Chiffres clés calculés en Python (jamais par le LLM) pour les tuiles de l'interface."""
    nums = _numeric_cols(df)
    if df.empty or not nums or df.shape == (1, 1):
        return []
    c = nums[0]
    label_col = _label_col(df, nums, label_col)
    s = pd.to_numeric(df[c], errors="coerce").dropna()
    if len(s) < 2:
        return []
    name = pretty(c)
    if label_col and _is_date_col(df[label_col]):
        ordered = df.loc[s.index].sort_values(label_col)
        first, last = ordered.iloc[0], ordered.iloc[-1]
        delta = None
        if first[c]:
            ratio = last[c] / first[c]
            if ratio >= 4:  # « +13207 % » est illisible : on affiche un multiplicateur
                delta = f"× {_fmt(round(float(ratio)))} depuis le début"
            else:
                pct = (last[c] - first[c]) / abs(first[c]) * 100
                delta = f"{pct:+.0f} % depuis le début"
        peak = s.idxmax()
        return [Highlight("Au début", _fmt(first[c]), help=f"{name} au {_fmt(first[label_col])}"),
                Highlight("À la fin", _fmt(last[c]), delta, help=f"{name} au {_fmt(last[label_col])}"),
                Highlight(f"Pic ({_fmt(df.at[peak, label_col])})", _fmt(s[peak]), help=name)]
    out = []
    if (s >= 0).all():
        out.append(Highlight("Total", _fmt(s.sum()), help=name))
    for title, idx in (("Plus élevé", s.idxmax()), ("Plus faible", s.idxmin())):
        who = _fmt(df.at[idx, label_col]) if label_col else None
        out.append(Highlight(f"{title} : {who}" if who else title, _fmt(s[idx]), help=name))
    return out


def build_messages(question: str, sql: str, df: pd.DataFrame, chart: str | None = None,
                   truncated: bool = False, label_col: str | None = None) -> list[dict]:
    user = [f"Question : {question}", f"SQL exécuté :\n{sql}",
            f"Affichage : {chart or 'tableau uniquement'}"]
    if truncated:
        user.append("Attention : le résultat a été tronqué à la limite d'affichage.")
    user.append(f"Résumé du résultat :\n{summarize(df, label_col)}")
    return [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "\n\n".join(user)}]


_JSON = re.compile(r"\{.*\}", re.S)
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def parse(raw: str) -> Explanation:
    """Lit la réponse JSON du LLM ; repli sur le texte brut si elle est mal formée."""
    text = _THINK.sub("", raw or "").strip()
    m = _JSON.search(text)
    if m:
        try:
            data = json.loads(m.group(0))
            points = []
            for p in data.get("points") or []:
                if isinstance(p, dict) and str(p.get("texte", "")).strip():
                    kind = str(p.get("type", "info")).lower()
                    points.append((kind if kind in POINT_TYPES else "info", str(p["texte"]).strip()))
                elif isinstance(p, str) and p.strip():
                    points.append(("info", p.strip()))
            title = str(data.get("titre", "")).strip()
            if title or points:
                return Explanation(title or points.pop(0)[1], points)
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass
    sentences = [x.strip() for x in _SENTENCE.split(text) if x.strip()]
    return Explanation(sentences[0] if sentences else text, [("info", x) for x in sentences[1:]])


def explain(llm, question: str, sql: str, df: pd.DataFrame, chart: str | None = None,
            truncated: bool = False, label_col: str | None = None) -> Explanation:
    """Renvoie l'explication structurée ; lève LLMError si l'appel échoue."""
    exp = parse(llm.chat(build_messages(question, sql, df, chart, truncated, label_col)))
    exp.highlights = highlights(df, label_col)
    return exp
