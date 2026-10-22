import pytest

from engine.llm import extract_sql
from engine.validator import validate

BLOCKED = {"factures", "clients", "encaissements", "banques", "etl_rejects"}


@pytest.mark.parametrize("sql", [
    "SELECT nom_banque, SUM(montant) FROM v_encaissements_detail GROUP BY 1",
    "WITH t AS (SELECT * FROM v_ca_mensuel) SELECT * FROM t;",
    "SELECT EXTRACT(YEAR FROM date_emission) FROM v_factures_detail",
    "SELECT client FROM v_ca_par_client WHERE client ILIKE '%delete%'",   # mot interdit dans un littéral
    "SELECT 1 -- DROP TABLE x",                                           # dans un commentaire
])
def test_accepts_valid_reads(sql):
    assert validate(sql, BLOCKED).ok


@pytest.mark.parametrize("sql", [
    "DROP TABLE factures",
    "DELETE FROM v_ca_mensuel",
    "SELECT 1; DROP TABLE factures",
    "SELECT * FROM etl_rejects",
    "SELECT * FROM v_ca_mensuel, factures",                 # jointure implicite sur table de base
    'SELECT * FROM "clients"',
    "SELECT pg_sleep(100)",
    "SELECT * FROM information_schema.tables",
    "SELECT * INTO nouvelle_table FROM v_ca_mensuel",
    "WITH x AS (DELETE FROM factures RETURNING *) SELECT * FROM x",
    "UPDATE factures SET statut = 'Payée'",
    "",
])
def test_rejects_dangerous_or_blocked(sql):
    assert not validate(sql, BLOCKED).ok


def test_extract_sql_variants():
    assert extract_sql("```sql\nSELECT 1\n```") == "SELECT 1"
    assert extract_sql("<think>blabla</think>\nSELECT 2") == "SELECT 2"
    assert extract_sql("Voici :\n```\nSELECT 3\n```") == "SELECT 3"
