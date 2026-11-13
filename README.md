# Assistant NL-to-SQL : BNS Engineering

Prototype de bout en bout conforme au cahier des charges : ETL CSV, PostgreSQL,
vues analytiques, génération SQL via Groq et interface Streamlit.

Le jeu de données actif est le Czech Financial Dataset. Les huit fichiers source
sont dans `data/czech/`; le schéma et les exemples NL-to-SQL sont adaptés à ces
données. Les anciennes données tunisiennes présentes dans `data/raw/` ne sont pas
utilisées par le pipeline actif.

## Installation (PowerShell)

Depuis ce dossier :

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env   # seulement si .env n'existe pas déjà
```

Configure les mots de passe PostgreSQL et `GROQ_API_KEY` dans `.env`, puis démarre
la base :

```powershell
docker compose up -d
docker compose ps
```

## Chargement et vérification des données

Le chargement réel recrée les tables et supprime les anciennes tables de démonstration.
Sauvegarde toute base existante avant de le lancer.

```powershell
python -m etl.run --dry-run
python -m etl.run
python -m engine.evaluate --check-refs
python -m pytest
```

Le mode `--dry-run` nettoie les CSV et met à jour le rapport ETL sans modifier
PostgreSQL. Le rapport détaille les lignes lues, doublons retirés et valeurs manquantes.

## Utilisation

Lance l'interface :

```powershell
python -m streamlit run app/streamlit_app.py
```

Ou interroge le moteur depuis le terminal :

```powershell
python -m engine.cli "Combien de comptes y a-t-il dans chaque district ?"
python -m engine.cli --schema
python -m engine.cli --models
```

L'interface affiche la requête SQL, le résultat en tableau ou graphique, et permet
de télécharger les résultats en CSV. Une carte « Ce qu'il faut retenir » explique le
résultat en langage naturel : une phrase de réponse, des chiffres clés (calculés en
Python, jamais par le modèle) et quelques observations. Elle se désactive dans la barre
latérale (un appel Groq de plus). En ligne de commande : `python -m engine.cli --explain "..."`. `python -m engine.evaluate` compare le moteur
aux requêtes de référence et écrit `reports/eval_report.md` (appels Groq facturables).

## Architecture et garde-fous

- `etl/` lit et normalise les huit CSV de `data/czech/`.
- `sql/01_schema.sql` définit les tables et relations ; `sql/02_views.sql` construit
  les vues analytiques exposées au modèle.
- `engine/` introspecte le schéma, appelle Groq, valide les requêtes et les exécute
  en lecture seule avec une limite de temps et de lignes.
- `app/` fournit l'interface de démonstration Streamlit.
- `tests/` contient les tests unitaires, exécutables avec `python -m pytest`.

Le validateur SQL est une première barrière, pas une frontière de sécurité. Configure
le rôle PostgreSQL en lecture seule (`RO_USER` / `RO_PASSWORD`) avant tout usage avec
des données réelles.
