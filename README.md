# Assistant NL-to-SQL : BNS Engineering

données brutes -> ETL -> PostgreSQL.
moteur NL-to-SQL (`engine/`) avec Groq.
vues analytiques (`sql/02_views.sql`), créées automatiquement par `python -m etl.run`.

## Installation

```bash
python -m venv .venv && source .venv/bin/activate     # Windows : .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # puis changer les mots de passe
docker compose up -d                                   # PostgreSQL 16 + utilisateur lecture seule
```

## Utilisation

```bash
python scripts/generate_data.py      # (optionnel) régénère les CSV synthétiques dans data/raw/
python -m etl.profile_data           # diagnostic qualité  -> reports/profiling_report.md
python -m etl.run --dry-run          # nettoie sans toucher la base
python -m etl.run                    # recrée le schéma et charge -> reports/etl_report.md
python -m etl.check_views            # vérifie les vues + 4 questions métier d'exemple
pytest                               # tests unitaires du nettoyage
```

## Principes

- **Tout est lu en texte** puis converti explicitement (pas de conversion silencieuse).
- **Aucune ligne n'est perdue sans trace** : les lignes rejetées sont stockées avec leur
  contenu brut et la raison dans la table `etl_rejects` et `reports/etl_rejects.csv`.
- **Schéma documenté** (`COMMENT ON` dans `sql/01_schema.sql`) : le moteur NL-to-SQL
  relira ces commentaires pour construire son prompt.
- **Utilisateur lecture seule** (`RO_USER`) pour le futur moteur : le LLM ne pourra jamais modifier la base.

## Remplacer les données

Déposer d'autres CSV dans `data/raw/` : `profile_data` fonctionne sur n'importe quel jeu ;
`clean.py`, `run.py` et `sql/01_schema.sql` sont à adapter aux nouvelles tables.

## Moteur NL-to-SQL (semaine 3)

1. Créer une clé sur https://console.groq.com/keys et la mettre dans `.env` (`GROQ_API_KEY=gsk_...`).
   Ne jamais la committer ni la partager.
2. Tester :

```bash
python -m engine.cli --models                       # modèles disponibles pour ta clé
python -m engine.cli "Montant total encaissé par banque ce mois-ci"
python -m engine.cli                                # mode interactif
python -m engine.cli --schema                       # schéma envoyé au LLM
python -m engine.evaluate --check-refs              # vérifie les SQL de référence (sans LLM)
python -m engine.evaluate                           # précision sur 20 questions -> reports/eval_report.md
```

Chaîne : question -> prompt (schéma lu automatiquement + règles + exemples) -> Groq -> validation SQL
(SELECT seul, relations autorisées) -> exécution (utilisateur lecture seule, READ ONLY, timeout)
-> si erreur, l'erreur est renvoyée au modèle pour correction (`MAX_RETRIES`).
