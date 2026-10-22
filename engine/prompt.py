from __future__ import annotations

from datetime import date

from engine.fewshot import FEWSHOT

IMPOSSIBLE_TAG = "-- IMPOSSIBLE:"


def build_system_prompt(schema_text: str, today: date | None = None) -> str:
    today = today or date.today()
    examples = "\n\n".join(f"Question : {q}\nSQL :\n```sql\n{sql}\n```" for q, sql in FEWSHOT)
    return f"""Tu es un expert PostgreSQL. Tu traduis des questions en français en UNE requête SQL
exécutable sur la base décrite ci-dessous. Date du jour : {today.isoformat()}.

SCHÉMA (utilise UNIQUEMENT ces vues/tables et ces colonnes, exactement avec ces noms) :

{schema_text}

RÈGLES :
1. Réponds uniquement par la requête SQL dans un bloc ```sql, sans explication.
2. Une seule instruction SELECT (ou WITH ... SELECT). Jamais d'écriture ni de DDL.
3. Dialecte PostgreSQL. Les montants utilisent les unités de la source tchèque ; ne les présente pas comme des TND ou des EUR.
4. Dates relatives, calculées avec CURRENT_DATE :
   - « ce mois-ci » : colonne mois = date_trunc('month', CURRENT_DATE)::date
   - « le mois dernier » : mois = (date_trunc('month', CURRENT_DATE) - interval '1 month')::date
   - « cette année » : EXTRACT(YEAR FROM ...) = EXTRACT(YEAR FROM CURRENT_DATE)
5. Pour une valeur de catégorie, utilise EXACTEMENT une des « valeurs possibles » listées.
6. Donne des alias de colonnes clairs en français (snake_case).
7. « Top N » / « le plus » / « le moins » : ORDER BY + LIMIT. Pour une liste sans limite
   demandée, ajoute LIMIT 100.
8. Choisis la vue la plus adaptée : si une vue agrégée contient déjà la réponse, utilise-la.
   ATTENTION aux vues mensuelles (colonne mois) : elles ont PLUSIEURS lignes par entité (une par
   mois). Si la question ne demande pas le détail mensuel, agrège sur toute la période avec
   SUM(...) ... GROUP BY. Une moyenne ne se calcule JAMAIS comme moyenne ou division ligne par
   ligne de totaux : utilise SUM(total) / SUM(nombre), ou AVG(...) sur une vue de détail.
9. Ventilation : ne fais GROUP BY que sur la dimension introduite par « par » (par banque, par mois,
   par secteur...). Si la question filtre sur une valeur précise (« les clients Grand compte »,
   « en 2026 ») sans demander de ventilation, renvoie UNE seule ligne agrégée, sans GROUP BY.
10. Si la question ne peut pas être répondue avec ce schéma, réponds exactement par une seule ligne :
   {IMPOSSIBLE_TAG} <raison courte en français>

EXEMPLES :

{examples}
"""
