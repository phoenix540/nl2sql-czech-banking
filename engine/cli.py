"""Interface console.

  python -m engine.cli "Montant total encaissé par banque ce mois-ci"
  python -m engine.cli                 (mode interactif)
  python -m engine.cli --schema        (affiche le schéma envoyé au LLM)
  python -m engine.cli --models        (liste les modèles Groq disponibles pour ta clé)
  python -m engine.cli --explain "..." (ajoute une explication en langage naturel du résultat)
"""
from __future__ import annotations

import sys

from engine import llm as llm_mod
from engine.pipeline import NL2SQL


def show(ans, bot=None, explain=False):
    print(f"\nSQL généré{' (après ' + str(len(ans.attempts) - 1) + ' correction(s))' if len(ans.attempts) > 1 else ''} :")
    print(ans.sql or "(aucun)")
    if ans.impossible:
        print(f"\nQuestion hors périmètre : {ans.impossible}")
    elif ans.ok:
        print(f"\n{len(ans.df)} ligne(s){' (tronqué)' if ans.truncated else ''}, {ans.seconds:.1f}s")
        print(ans.df.head(25).to_string(index=False))
        if explain and bot is not None and not ans.df.empty:
            try:
                print(f"\nExplication :\n{bot.explain(ans).as_text()}")
            except Exception as exc:  # noqa: BLE001
                print(f"\nExplication indisponible : {exc}")
    else:
        print(f"\nÉchec : {ans.error}")


def main(argv):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if "--models" in argv:
        print("\n".join(llm_mod.list_models()))
        return
    bot = NL2SQL.from_env()
    if "--schema" in argv:
        print(bot.schema_text)
        return
    print(f"Modèle : {bot.llm.model} | Sécurité : {bot.security_mode}")
    explain = "--explain" in argv
    questions = [a for a in argv if not a.startswith("--")]
    if questions:
        show(bot.ask(" ".join(questions)), bot, explain)
        return
    while True:
        try:
            q = input("\nQuestion (vide pour quitter) > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            break
        show(bot.ask(q), bot, explain)


if __name__ == "__main__":
    main(sys.argv[1:])
