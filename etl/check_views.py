"""Vérifie les vues analytiques du Czech Financial Dataset."""
from sqlalchemy import create_engine, text
from etl.config import db_url

VIEWS = ["v_districts", "v_clients", "v_accounts", "v_dispositions", "v_cards", "v_loans", "v_orders", "v_transactions", "v_account_activity", "v_transactions_monthly", "v_loan_summary", "v_client_accounts", "v_district_summary"]
QUESTIONS = {
    "Top comptes par activité": "SELECT account_id, transaction_count FROM v_account_activity ORDER BY transaction_count DESC LIMIT 5",
    "Nombre de prêts par statut": "SELECT status_description, COUNT(*) AS n FROM v_loans GROUP BY status_description ORDER BY n DESC",
    "Comptes par district": "SELECT district_name, account_count FROM v_district_summary ORDER BY account_count DESC LIMIT 10",
}
def main(eng=None):
    eng = eng or create_engine(db_url())
    with eng.connect() as c:
        for v in VIEWS:
            n = c.execute(text(f'SELECT count(*) FROM "{v}"')).scalar_one()
            print(f"{v:30s} {n:>10,d} lignes")
        for q, sql in QUESTIONS.items():
            print(f"\n> {q}")
            for row in c.execute(text(sql)).fetchmany(6):
                print("  ", tuple(row))
if __name__ == "__main__":
    main()
