"""Fonctions de nettoyage. Chaque fonction prend un DataFrame brut (toutes les
colonnes en texte) et renvoie un DataFrame propre ; les lignes ecartees et les
corrections sont consignees dans un objet Report.
"""
from __future__ import annotations

import json
import re
import unicodedata

import pandas as pd

FR_DATE = re.compile(r"^\d{2}/\d{2}/\d{4}$")

STATUT_MAP = {
    "payee": "Payée",
    "impayee": "Impayée",
    "partiellement payee": "Partiellement payée",
    "part. payee": "Partiellement payée",
    "partiel": "Partiellement payée",
    "en attente": "En attente",
}
MODE_MAP = {
    "virement": "Virement",
    "cheque": "Chèque",
    "traite": "Traite",
    "prelevement": "Prélèvement",
    "especes": "Espèces",
}
OUTLIER_FACTOR = 20  # montant > 20 x percentile 99 => aberrant


# ------------------------------------------------------------------ utilitaires
def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def norm_key(s) -> str:
    return strip_accents(str(s)).strip().lower()


def parse_mixed_dates(series: pd.Series) -> pd.Series:
    """Accepte AAAA-MM-JJ et JJ/MM/AAAA (jamais d'ambiguite : format explicite)."""
    s = series.astype("string").str.strip()
    iso = pd.to_datetime(s, format="%Y-%m-%d", errors="coerce")
    fr = pd.to_datetime(s, format="%d/%m/%Y", errors="coerce")
    return iso.fillna(fr)


def parse_amount(series: pd.Series) -> pd.Series:
    s = (series.astype("string").str.strip()
         .str.replace(r"\s", "", regex=True).str.replace(",", ".", regex=False))
    return pd.to_numeric(s, errors="coerce")


def to_int(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype("string").str.strip(), errors="coerce").astype("Int64")


class Report:
    def __init__(self):
        self.actions: list[tuple[str, str, int]] = []
        self.rejects: list[pd.DataFrame] = []

    def act(self, table: str, msg: str, n: int):
        if int(n):
            self.actions.append((table, msg, int(n)))

    def reject(self, table: str, raw_rows: pd.DataFrame, reason: str):
        if len(raw_rows) == 0:
            return
        payload = raw_rows.astype(object).where(raw_rows.notna(), None).apply(
            lambda r: json.dumps(r.to_dict(), ensure_ascii=False, default=str), axis=1)
        self.rejects.append(pd.DataFrame(
            {"table_name": table, "reason": reason, "source_row": payload.values}))
        self.act(table, f"REJETÉ : {reason}", len(raw_rows))

    def rejects_df(self) -> pd.DataFrame:
        if not self.rejects:
            return pd.DataFrame(columns=["table_name", "reason", "source_row"])
        return pd.concat(self.rejects, ignore_index=True)


def _dedupe_pk(df, pk, table, rep):
    dup = df.duplicated(pk, keep="first")
    rep.act(table, f"doublons sur `{pk}` supprimés", dup.sum())
    return df[~dup]


def _strip_cols(df, cols, table, rep):
    for c in cols:
        before = df[c].astype("string")
        after = before.str.strip().str.replace(r"\s+", " ", regex=True)
        rep.act(table, f"`{c}` : espaces parasites retirés", ((before != after) & before.notna()).sum())
        df[c] = after
    return df


def _dates(df, col, table, rep):
    raw = df[col].astype("string").str.strip()
    rep.act(table, f"`{col}` : dates JJ/MM/AAAA converties au format ISO",
            raw.str.match(FR_DATE, na=False).sum())
    parsed = parse_mixed_dates(df[col])
    rep.act(table, f"`{col}` : valeurs non interprétables -> NULL", (parsed.isna() & raw.notna()).sum())
    df[col] = parsed.dt.date.where(parsed.notna(), None)
    return df


def _apply_checks(df, snapshot, table, rep, checks):
    """Applique les tests un par un ; les lignes rejetées sont journalisées
    avec leur contenu BRUT d'origine (snapshot)."""
    for test, reason in checks:
        mask = test(df).fillna(False).astype(bool)
        rep.reject(table, snapshot.loc[df.index[mask]], reason)
        df = df[~mask]
    return df


# ------------------------------------------------------------------ tables
def clean_banques(raw: pd.DataFrame, rep: Report) -> pd.DataFrame:
    df = raw.copy()
    df = _dedupe_pk(df, "banque_id", "banques", rep)
    df = _strip_cols(df, ["nom_banque", "code_banque", "raison_sociale_banque"], "banques", rep)
    df["banque_id"] = to_int(df["banque_id"])
    return df


def clean_clients(raw: pd.DataFrame, rep: Report) -> pd.DataFrame:
    df = raw.copy()
    df = _dedupe_pk(df, "client_id", "clients", rep)
    df = _strip_cols(df, ["raison_sociale", "secteur", "ville", "segment"], "clients", rep)
    new_ville = df["ville"].str.title()
    rep.act("clients", "`ville` : casse normalisée (TUNIS -> Tunis)",
            ((df["ville"] != new_ville) & df["ville"].notna()).sum())
    df["ville"] = new_ville
    rep.act("clients", "`ville` : valeurs manquantes (laissées NULL)", df["ville"].isna().sum())
    rep.act("clients", "`secteur` : valeurs manquantes (laissées NULL)", df["secteur"].isna().sum())
    df["client_id"] = to_int(df["client_id"])
    df = _dates(df, "date_creation", "clients", rep)
    return df


def clean_factures(raw: pd.DataFrame, rep: Report, valid_clients: set) -> pd.DataFrame:
    df = _dedupe_pk(raw.copy(), "facture_id", "factures", rep)
    snapshot = df.copy()
    df["facture_id"] = to_int(df["facture_id"])
    df["client_id"] = to_int(df["client_id"])
    df = _dates(df, "date_emission", "factures", rep)
    df = _dates(df, "date_echeance", "factures", rep)
    for c in ["montant_ht", "montant_tva", "montant_ttc"]:
        df[c] = parse_amount(df[c])

    # statut canonique
    keys = df["statut"].map(lambda v: norm_key(v) if pd.notna(v) else None)
    mapped = keys.map(STATUT_MAP)
    rep.act("factures", "`statut` : libellés harmonisés",
            ((mapped != df["statut"]) & mapped.notna()).sum())
    df["statut"] = mapped

    # TTC = HT + TVA
    expected = (df["montant_ht"] + df["montant_tva"]).round(3)
    bad = ((df["montant_ttc"] - expected).abs() > 0.01) & expected.notna()
    rep.act("factures", "`montant_ttc` recalculé (HT + TVA)", bad.sum())
    df.loc[bad, "montant_ttc"] = expected[bad]

    # échéance incohérente -> NULL
    bad_due = df["date_echeance"].notna() & (
        pd.to_datetime(df["date_echeance"]) <= pd.to_datetime(df["date_emission"]))
    rep.act("factures", "`date_echeance` <= émission invalidée (NULL)", bad_due.sum())
    df.loc[bad_due, "date_echeance"] = None
    rep.act("factures", "`date_echeance` : valeurs manquantes (NULL)", df["date_echeance"].isna().sum())

    # rejets (chaque test est évalué sur le DataFrame déjà filtré)
    amt = ["montant_ht", "montant_tva", "montant_ttc"]
    checks = [
        (lambda d: d["date_emission"].isna(), "date_emission invalide"),
        (lambda d: d[amt].isna().any(axis=1) | (d[amt] < 0).any(axis=1), "montant invalide ou négatif"),
        (lambda d: d["statut"].isna(), "statut inconnu"),
        (lambda d: ~d["client_id"].isin(valid_clients), "client inexistant"),
    ]
    return _apply_checks(df, snapshot, "factures", rep, checks)


def clean_encaissements(raw: pd.DataFrame, rep: Report, valid_factures: set,
                        valid_banques: set) -> pd.DataFrame:
    df = _dedupe_pk(raw.copy(), "encaissement_id", "encaissements", rep)
    snapshot = df.copy()
    df["encaissement_id"] = to_int(df["encaissement_id"])
    df["facture_id"] = to_int(df["facture_id"])
    df["banque_id"] = to_int(df["banque_id"])
    df = _dates(df, "date_encaissement", "encaissements", rep)

    decimal_comma = df["montant"].astype("string").str.contains(",", na=False).sum()
    rep.act("encaissements", "`montant` : virgule décimale convertie", decimal_comma)
    df["montant"] = parse_amount(df["montant"])

    # mode de paiement
    keys = df["mode_paiement"].map(lambda v: norm_key(v) if pd.notna(v) else None)
    mapped = keys.map(MODE_MAP)
    rep.act("encaissements", "`mode_paiement` : casse/libellés harmonisés",
            ((mapped != df["mode_paiement"]) & mapped.notna()).sum())
    rep.act("encaissements", "`mode_paiement` manquant -> 'Non renseigné'", df["mode_paiement"].isna().sum())
    df["mode_paiement"] = mapped.fillna("Non renseigné")

    rep.act("encaissements", "`banque_id` manquant (laissé NULL, banque inconnue)", df["banque_id"].isna().sum())

    pos = df["montant"][df["montant"] > 0]
    cap = OUTLIER_FACTOR * pos.quantile(0.99) if len(pos) else float("inf")
    checks = [
        (lambda d: d["date_encaissement"].isna(), "date_encaissement invalide"),
        (lambda d: d["montant"].isna(), "montant non numérique"),
        (lambda d: d["montant"] <= 0, "montant <= 0"),
        (lambda d: d["montant"] > cap, f"montant aberrant (> {OUTLIER_FACTOR} x P99 = {cap:,.0f})"),
        (lambda d: ~d["facture_id"].isin(valid_factures), "facture inexistante (orphelin)"),
        (lambda d: d["banque_id"].notna() & ~d["banque_id"].isin(valid_banques), "banque inexistante"),
    ]
    return _apply_checks(df, snapshot, "encaissements", rep, checks)
