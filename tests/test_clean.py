import pandas as pd

from etl import clean


def test_mixed_dates():
    s = pd.Series(["2026-03-05", "05/03/2026", None, "garbage"])
    out = clean.parse_mixed_dates(s)
    assert out[0] == out[1] == pd.Timestamp("2026-03-05")
    assert pd.isna(out[2]) and pd.isna(out[3])


def test_amount_decimal_comma():
    out = clean.parse_amount(pd.Series(["1234,567", "89.5", "x"]))
    assert out[0] == 1234.567 and out[1] == 89.5 and pd.isna(out[2])


def test_statut_variants_harmonised():
    rep = clean.Report()
    raw = pd.DataFrame({
        "facture_id": ["1", "2", "3"], "client_id": ["1"] * 3,
        "date_emission": ["2026-01-01", "02/01/2026", "2026-01-03"],
        "date_echeance": ["2026-02-01", None, "2026-01-03"],
        "montant_ht": ["100", "200", "300"], "montant_tva": ["19", "38", "57"],
        "montant_ttc": ["119", "999", "357"],
        "statut": ["PAYEE", "partiel", "Part. payée"],
    })
    out = clean.clean_factures(raw, rep, valid_clients={1})
    assert list(out["statut"]) == ["Payée", "Partiellement payée", "Partiellement payée"]
    assert float(out.loc[out.facture_id == 2, "montant_ttc"].iloc[0]) == 238.0  # recalculé
    assert out.loc[out.facture_id == 3, "date_echeance"].isna().all()           # échéance == émission


def test_encaissements_rejects_are_logged_not_lost():
    rep = clean.Report()
    raw = pd.DataFrame({
        "encaissement_id": ["1", "2", "3", "4"], "facture_id": ["1", "1", "1", "99"],
        "banque_id": ["1.0", None, "1", "1"],
        "date_encaissement": ["2026-01-01"] * 4,
        "montant": ["100,5", "-5", "50", "70"],
        "mode_paiement": ["virement", None, "Chèque", "traite"],
        "reference": list("abcd"),
    })
    out = clean.clean_encaissements(raw, rep, valid_factures={1}, valid_banques={1})
    assert set(out["encaissement_id"]) == {1, 3}
    reasons = set(rep.rejects_df()["reason"])
    assert "montant <= 0" in reasons and any("orphelin" in r for r in reasons)
    assert out.loc[out.encaissement_id == 1, "mode_paiement"].iloc[0] == "Virement"
