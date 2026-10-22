"""Mesure la précision du moteur : compare le résultat du SQL généré à celui du SQL de référence.

  python -m engine.evaluate               (appelle Groq : ~20 requêtes)
  python -m engine.evaluate --check-refs  (vérifie seulement que les SQL de référence s'exécutent)
"""
from __future__ import annotations

import math
import sys
import time
from datetime import date, datetime
from decimal import Decimal

from engine import executor
from engine.eval_set import EVAL_SET
from engine.pipeline import NL2SQL
from etl.config import REPORTS_DIR


def _norm(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if isinstance(v, (int, float, Decimal)):
        return round(float(v), 2)
    if isinstance(v, (date, datetime)):
        return str(v)[:10]
    return str(v).strip()


def _cols(df):
    return [sorted((_norm(v) for v in df[c]), key=repr) for c in df.columns]


def compare(ref, gen) -> str:
    """'exact' | 'colonnes en plus' | 'faux'"""
    if gen is None or len(ref) != len(gen):
        return "faux"
    rc, gc = _cols(ref), _cols(gen)
    rows = lambda d: sorted((tuple(_norm(v) for v in r) for r in d.itertuples(index=False)), key=repr)
    if len(ref.columns) == len(gen.columns) and rows(ref) == rows(gen):
        return "exact"
    used = set()
    for col in rc:
        j = next((i for i, g in enumerate(gc) if i not in used and g == col), None)
        if j is None:
            return "faux"
        used.add(j)
    return "colonnes en plus"


def run(bot: NL2SQL, pause: float = 1.0):
    results = []
    for q, ref_sql in EVAL_SET:
        ref = executor.run_query(bot.engine, ref_sql)
        ans = bot.ask(q)
        verdict = "faux" if not ans.ok or ref.error else compare(ref.df, ans.df)
        results.append({"question": q, "verdict": verdict, "retries": max(len(ans.attempts) - 1, 0),
                        "seconds": ans.seconds, "sql": ans.sql, "error": ans.error or ref.error})
        print(f"[{verdict:16s}] {q}")
        time.sleep(pause)
    good = sum(r["verdict"] != "faux" for r in results)
    exact = sum(r["verdict"] == "exact" for r in results)
    print(f"\nPrécision : {good}/{len(results)} ({good / len(results):.0%}) dont {exact} exactes")
    return results


def write_report(results, model):
    good = sum(r["verdict"] != "faux" for r in results)
    lines = [f"# Évaluation NL-to-SQL\n", f"Modèle : `{model}`  |  Précision : **{good}/{len(results)}**\n",
             "| Question | Verdict | Corrections | Temps (s) |", "|---|---|---|---|"]
    lines += [f"| {r['question']} | {r['verdict']} | {r['retries']} | {r['seconds']:.1f} |" for r in results]
    fails = [r for r in results if r["verdict"] == "faux"]
    if fails:
        lines += ["", "## Échecs détaillés\n"]
        for r in fails:
            lines += [f"**{r['question']}**", f"```sql\n{r['sql']}\n```", f"Erreur : {r['error']}\n"]
    REPORTS_DIR.mkdir(exist_ok=True)
    (REPORTS_DIR / "eval_report.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if "--check-refs" in argv:
        eng, _ = executor.make_engine()
        bad = 0
        for q, sql in EVAL_SET:
            r = executor.run_query(eng, sql)
            bad += r.error is not None
            print(f"[{'ERREUR' if r.error else 'ok':6s}] {q} {r.error or ''}")
        print(f"\n{len(EVAL_SET) - bad}/{len(EVAL_SET)} requêtes de référence valides")
        return
    bot = NL2SQL.from_env()
    res = run(bot)
    write_report(res, bot.llm.model)
    print("Rapport : reports/eval_report.md")


if __name__ == "__main__":
    main(sys.argv[1:])
