# Czech dataset migration patch

This patch replaces the ETL/schema/views and NL-to-SQL example sets for the Czech Financial Dataset.

## Before you apply
1. Back up your project folder and database.
2. Confirm the eight source CSVs are in `data/czech/`: `account.csv`, `card.csv`, `client.csv`, `disp.csv`, `district.csv`, `loan.csv`, `order.csv`, `trans.csv`.
3. Copy the contents of this patch folder into the project root, allowing these files to be overwritten: `etl/config.py`, `etl/run.py`, `sql/01_schema.sql`, `sql/02_views.sql`, `engine/fewshot.py`, `engine/eval_set.py`, `engine/prompt.py`, `etl/profile_data.py`, `etl/check_views.py`, and `app/streamlit_app.py`.

## Important design choices
- `order.csv` is loaded into a table named `bank_order` because `ORDER` is a SQL keyword.
- `district` preserves the original A1..A16 column names; district ID is `district."A1"`.
- Dates in YYMMDD format are parsed with Python's `%y%m%d` convention. Check the resulting date range in the ETL report.
- The loader removes exact duplicate rows and duplicate primary keys, keeping the first occurrence, and reports those counts. Review the report before production use.
- The SQL schema script drops the legacy Tunisian tables and creates Czech tables. Back up the database before running the real load.
- Analytical views aggregate transactions, dispositions, loans and district counts separately before joining, to avoid inflating totals through join multiplication.

## Run
From the project root:

```bat
python -m etl.run --dry-run
```

If the report and date parsing look reasonable, and after backing up the database:

```bat
python -m etl.run
```

Then run the tests:

```bat
python -m pytest
```

The `--dry-run` command does not connect to or modify PostgreSQL. The full ETL drops the old demo schema through `sql/01_schema.sql`.

Note: the schema introspection exposes only `v_*` views, so the examples and evaluation SQL query those views rather than the base tables.
