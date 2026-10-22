"""ETL Czech Financial Dataset CSV -> PostgreSQL.

Place les 8 CSV d'origine dans data/czech/. Les fichiers utilisent le séparateur ';'.
Usage : python -m etl.run --dry-run (profilage/nettoyage sans toucher PostgreSQL)
        python -m etl.run             (recrée les tables et recharge les données)
"""
from __future__ import annotations
import argparse, json, time
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text
from etl.config import CZECH_DIR, REPORTS_DIR, SQL_DIR, db_url

FILES = ["district", "client", "account", "disp", "card", "loan", "bank_order", "trans"]
SOURCE_FILES = {"district":"district.csv", "client":"client.csv", "account":"account.csv",
                "disp":"disp.csv", "card":"card.csv", "loan":"loan.csv", "bank_order":"order.csv", "trans":"trans.csv"}
DATE_COLUMNS = {"account":["date"], "card":["issued"], "loan":["date"], "trans":["date"]}
INT_COLUMNS = {"district":["A1"], "client":["client_id","district_id"],
 "account":["account_id","district_id"], "disp":["disp_id","client_id","account_id"],
 "card":["card_id","disp_id"], "loan":["loan_id","account_id","duration"],
 "bank_order":["order_id","account_id"], "trans":["trans_id","account_id"]}
NUM_COLUMNS = {"district":["A4","A5","A6","A7","A8","A9","A10","A11","A12","A13","A14","A15","A16"],
 "loan":["amount","payments"], "bank_order":["amount"], "trans":["amount","balance"]}

def parse_czech_date(series: pd.Series) -> pd.Series:
    """Parse YYMMDD; card.issued peut aussi contenir 'YYMMDD 00:00:00'."""
    s = series.astype("string").str.strip().str.slice(0, 6)
    parsed = pd.to_datetime(s, format="%y%m%d", errors="coerce")
    return parsed.dt.date.where(parsed.notna(), None)

def read_and_clean(table: str) -> tuple[pd.DataFrame, dict]:
    path = CZECH_DIR / SOURCE_FILES[table]
    if not path.is_file():
        raise FileNotFoundError(f"CSV manquant : {path}")
    # dtype=str préserve notamment les numéros de compte externes et birth_number.
    df = pd.read_csv(path, sep=";", dtype=str, keep_default_na=True, encoding="utf-8-sig")
    initial = len(df)
    df.columns = [c.strip() for c in df.columns]
    # Normalisation légère des champs texte, sans traduire les catégories originales.
    for col in df.select_dtypes(include=["object", "string"]).columns:
        df[col] = df[col].astype("string").str.strip().replace({"": pd.NA})
    # La table source district.csv contient A1..A16; les noms sont conservés pour fidélité.
    for col in INT_COLUMNS.get(table, []):
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    for col in NUM_COLUMNS.get(table, []):
        if col in df:
            df[col] = pd.to_numeric(df[col].str.replace(",", ".", regex=False), errors="coerce")
    for col in DATE_COLUMNS.get(table, []):
        if col in df:
            df[col] = parse_czech_date(df[col])
    # Supprime uniquement les doublons exacts; les collisions de PK sont signalées.
    exact_duplicates = int(df.duplicated().sum())
    if exact_duplicates:
        df = df.drop_duplicates().copy()
    pk = {"district":"A1", "client":"client_id", "account":"account_id", "disp":"disp_id",
          "card":"card_id", "loan":"loan_id", "bank_order":"order_id", "trans":"trans_id"}[table]
    duplicate_pk = int(df[pk].duplicated().sum())
    if duplicate_pk:
        # Garder la première ligne stable, mais signaler explicitement dans le rapport.
        df = df.drop_duplicates(pk, keep="first").copy()
    info = {"table":table, "source":SOURCE_FILES[table], "rows_raw":initial,
            "rows_loaded":len(df), "exact_duplicates_removed":exact_duplicates,
            "duplicate_primary_keys_removed":duplicate_pk,
            "missing_values":int(df.isna().sum().sum())}
    return df, info

def write_report(reports: list[dict]) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    lines = ["# Czech Financial Dataset — rapport ETL", "", "| Table PostgreSQL | CSV source | Lignes source | Lignes chargées | Doublons exacts retirés | PK dupliquées retirées | Valeurs manquantes |", "|---|---|---:|---:|---:|---:|---:|"]
    for x in reports:
        lines.append(f"| {x['table']} | {x['source']} | {x['rows_raw']} | {x['rows_loaded']} | {x['exact_duplicates_removed']} | {x['duplicate_primary_keys_removed']} | {x['missing_values']} |")
    (REPORTS_DIR / "etl_report.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    (REPORTS_DIR / "etl_report.json").write_text(json.dumps(reports, indent=2, ensure_ascii=False), encoding="utf-8")

def load(cleaned: dict[str, pd.DataFrame]) -> None:
    eng = create_engine(db_url(), future=True)
    t0 = time.time()
    with eng.begin() as conn:
        # DDL includes DROP statements: run only after reviewing/backup.
        conn.exec_driver_sql((SQL_DIR / "01_schema.sql").read_text(encoding="utf-8"))
        for name in FILES:
            df = cleaned[name]
            df.to_sql(name, conn, if_exists="append", index=False, chunksize=3000, method="multi")
            print(f"Loaded {name}: {len(df):,} rows")
        conn.exec_driver_sql((SQL_DIR / "02_views.sql").read_text(encoding="utf-8"))
    with eng.connect() as conn:
        for name in FILES:
            actual = conn.execute(text(f'SELECT count(*) FROM "{name}"')).scalar_one()
            expected = len(cleaned[name])
            print(f"{name:12s} {actual:>10,} rows [{'OK' if actual == expected else 'MISMATCH'}]")
    eng.dispose()
    print(f"Load completed in {time.time()-t0:.1f}s")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="read/clean/report only; no database writes")
    args = ap.parse_args()
    cleaned, reports = {}, []
    for table in FILES:
        df, info = read_and_clean(table)
        cleaned[table] = df
        reports.append(info)
        print(f"{table:12s}: {info['rows_raw']:,} source -> {info['rows_loaded']:,} loaded; "
              f"{info['exact_duplicates_removed']} exact duplicates; {info['duplicate_primary_keys_removed']} duplicate PKs")
    write_report(reports)
    print(f"Report written to {REPORTS_DIR / 'etl_report.md'}")
    if args.dry_run:
        print("Dry run: PostgreSQL was not modified.")
        return
    load(cleaned)

if __name__ == "__main__":
    main()
