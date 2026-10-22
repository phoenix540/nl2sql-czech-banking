"""
Générateur de données synthétiques - projet NL-to-SQL (BNS Engineering)
Domaine : facturation clients et encaissements bancaires (contexte tunisien).

Produit 4 CSV "bruts" dans ./data/ avec des anomalies volontaires
(valeurs manquantes, doublons, formats de date mixtes, libellés incohérents...)
pour exercer la phase ETL. Reproductible via SEED.

Usage : python generate_data.py
"""
import random
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
random.seed(SEED)
rng = np.random.default_rng(SEED)

OUT = Path(__file__).resolve().parents[1] / "data" / "raw"
OUT.mkdir(parents=True, exist_ok=True)

TODAY = date(2026, 10, 19)
START = date(2025, 4, 1)  # ~18 mois d'historique

# ---------------------------------------------------------------- banques
BANQUES = [
    ("BIAT", "08", "Banque Internationale Arabe de Tunisie"),
    ("STB", "10", "Société Tunisienne de Banque"),
    ("BNA", "03", "Banque Nationale Agricole"),
    ("Amen Bank", "07", "Amen Bank"),
    ("ATB", "01", "Arab Tunisian Bank"),
    ("UIB", "12", "Union Internationale de Banques"),
    ("Attijari Bank", "04", "Attijari Bank Tunisie"),
    ("BH Bank", "14", "Banque de l'Habitat"),
    ("Zitouna", "25", "Banque Zitouna"),
    ("BT", "05", "Banque de Tunisie"),
]
banques = pd.DataFrame(
    [(i + 1, n, c, f) for i, (n, c, f) in enumerate(BANQUES)],
    columns=["banque_id", "nom_banque", "code_banque", "raison_sociale_banque"],
)
# poids de chaque banque dans les encaissements
bank_w = np.array([0.18, 0.12, 0.11, 0.12, 0.08, 0.08, 0.10, 0.07, 0.06, 0.08])

# ---------------------------------------------------------------- clients
VILLES = ["Tunis", "Ariana", "Sfax", "Sousse", "Nabeul", "Bizerte", "Monastir",
          "Gabès", "Kairouan", "Ben Arous", "La Marsa", "Gafsa"]
SECTEURS = ["Industrie", "Commerce", "Services", "Agroalimentaire",
            "Transport", "BTP", "Santé", "Énergie", "Technologies"]
SEGMENTS = ["Grand compte", "PME", "TPE"]
PREFIX = ["Sotu", "Tuni", "Medi", "Carthage", "Atlas", "Sahel", "Zeus", "Delta",
          "Orient", "Nova", "Kasbah", "Djerba", "Oasis", "Phénix", "Cap",
          "Hannibal", "Salammbô", "Utique", "Médina", "Olivier", "Jasmin", "Baraka"]
SUFFIX = ["Industries", "Distribution", "Conseil", "Logistique", "Group",
          "Services", "Agro", "Construction", "Pharma", "Énergie", "Tech", "Trading"]

N_CLIENTS = 220
noms = set()
while len(noms) < N_CLIENTS:
    noms.add(f"{random.choice(PREFIX)} {random.choice(SUFFIX)}")
noms = sorted(noms)
seg = rng.choice(SEGMENTS, N_CLIENTS, p=[0.15, 0.40, 0.45])
clients = pd.DataFrame({
    "client_id": np.arange(1, N_CLIENTS + 1),
    "raison_sociale": noms,
    "secteur": rng.choice(SECTEURS, N_CLIENTS),
    "ville": rng.choice(VILLES, N_CLIENTS, p=[.22, .10, .12, .10, .06, .05, .05, .04, .03, .09, .08, .06]),
    "segment": seg,
    "date_creation": [
        (date(2015, 1, 1) + timedelta(days=int(rng.integers(0, 3600)))).isoformat()
        for _ in range(N_CLIENTS)
    ],
})
seg_scale = {"Grand compte": 45000, "PME": 9000, "TPE": 2200}
seg_freq = {"Grand compte": 3.0, "PME": 1.6, "TPE": 0.8}  # factures / mois

# ---------------------------------------------------------------- factures
rows = []
fid = 1
d = START
months = pd.period_range(START, TODAY, freq="M")
for m in months:
    month_start = m.start_time.date()
    month_end = min(m.end_time.date(), TODAY)
    n_days = (month_end - month_start).days + 1
    for _, c in clients.iterrows():
        k = rng.poisson(seg_freq[c["segment"]])
        for _ in range(k):
            emission = month_start + timedelta(days=int(rng.integers(0, n_days)))
            echeance = emission + timedelta(days=int(rng.choice([30, 45, 60])))
            ht = round(float(rng.lognormal(np.log(seg_scale[c["segment"]]), 0.6)), 3)
            tva = round(ht * 0.19, 3)
            rows.append([fid, c["client_id"], emission, echeance, ht, tva, round(ht + tva, 3)])
            fid += 1
factures = pd.DataFrame(rows, columns=[
    "facture_id", "client_id", "date_emission", "date_echeance",
    "montant_ht", "montant_tva", "montant_ttc"])

# statut selon l'ancienneté
def statut(row):
    age = (TODAY - row["date_emission"]).days
    r = rng.random()
    if age > 120:
        return "Payée" if r < 0.93 else ("Partiellement payée" if r < 0.97 else "Impayée")
    if age > 45:
        return "Payée" if r < 0.70 else ("Partiellement payée" if r < 0.82 else "Impayée")
    return "Payée" if r < 0.30 else ("Partiellement payée" if r < 0.38 else "En attente")
factures["statut"] = factures.apply(statut, axis=1)

# ---------------------------------------------------------------- encaissements
MODES = ["Virement", "Chèque", "Traite", "Prélèvement", "Espèces"]
mode_w = [0.50, 0.25, 0.12, 0.08, 0.05]
enc = []
eid = 1
for _, f in factures.iterrows():
    if f["statut"] in ("En attente", "Impayée"):
        continue
    parts = 1 if f["statut"] == "Payée" else 1
    montant_total = f["montant_ttc"] if f["statut"] == "Payée" else round(f["montant_ttc"] * rng.uniform(0.3, 0.8), 3)
    # paiement en 1 ou 2 tranches pour 15% des factures payées
    tranches = [montant_total]
    if f["statut"] == "Payée" and rng.random() < 0.15:
        a = round(montant_total * rng.uniform(0.4, 0.7), 3)
        tranches = [a, round(montant_total - a, 3)]
    delay = int(max(0, rng.normal(f["date_echeance"].toordinal() - f["date_emission"].toordinal() - 5, 12)))
    for t in tranches:
        dt = f["date_emission"] + timedelta(days=delay + int(rng.integers(0, 10)))
        if dt > TODAY:
            continue
        enc.append([eid, f["facture_id"],
                    int(rng.choice(banques["banque_id"], p=bank_w)),
                    dt, t, rng.choice(MODES, p=mode_w),
                    f"REF{dt:%y%m}{eid:06d}"])
        eid += 1
encaissements = pd.DataFrame(enc, columns=[
    "encaissement_id", "facture_id", "banque_id", "date_encaissement",
    "montant", "mode_paiement", "reference"])

# =============================================================== ANOMALIES
log = []

def pick(df, frac):
    return df.sample(frac=frac, random_state=SEED).index

# --- clients
clients["ville"] = clients["ville"].astype(object)
idx = pick(clients, 0.06); clients.loc[idx, "ville"] = None
log.append(("clients", "ville", f"{len(idx)} valeurs manquantes"))
idx = pick(clients, 0.08)
clients.loc[idx, "ville"] = clients.loc[idx, "ville"].map(
    lambda v: v.upper() if isinstance(v, str) else v)
log.append(("clients", "ville", f"{len(idx)} valeurs en MAJUSCULES (casse incohérente)"))
idx = pick(clients, 0.05)
clients.loc[idx, "raison_sociale"] = clients.loc[idx, "raison_sociale"].map(lambda v: f"  {v} ")
log.append(("clients", "raison_sociale", f"{len(idx)} valeurs avec espaces parasites"))
idx = pick(clients, 0.04)
clients.loc[idx, "secteur"] = None
log.append(("clients", "secteur", f"{len(idx)} valeurs manquantes"))
# date_creation: quelques formats DD/MM/YYYY
idx = pick(clients, 0.10)
clients.loc[idx, "date_creation"] = clients.loc[idx, "date_creation"].map(
    lambda s: pd.to_datetime(s).strftime("%d/%m/%Y"))
log.append(("clients", "date_creation", f"{len(idx)} dates au format JJ/MM/AAAA (le reste en ISO)"))

# --- factures
factures["date_emission"] = factures["date_emission"].astype(str)
factures["date_echeance"] = factures["date_echeance"].astype(str)
idx = pick(factures, 0.07)
factures.loc[idx, "date_emission"] = factures.loc[idx, "date_emission"].map(
    lambda s: pd.to_datetime(s).strftime("%d/%m/%Y"))
log.append(("factures", "date_emission", f"{len(idx)} dates au format JJ/MM/AAAA"))
idx = pick(factures, 0.02); factures.loc[idx, "date_echeance"] = None
log.append(("factures", "date_echeance", f"{len(idx)} valeurs manquantes"))
# statut : variantes de libellés
variants = {"Payée": ["payee", "PAYEE", "Payee"], "Impayée": ["impayee", "IMPAYEE"],
            "Partiellement payée": ["Part. payée", "partiel"]}
idx = pick(factures, 0.10)
factures["statut"] = factures["statut"].astype(object)
for i in idx:
    s = factures.at[i, "statut"]
    if s in variants:
        factures.at[i, "statut"] = random.choice(variants[s])
log.append(("factures", "statut", f"~{len(idx)} libellés incohérents (payee/PAYEE/partiel...)"))
# montant_ttc incohérent avec ht+tva
idx = pick(factures, 0.01)
factures.loc[idx, "montant_ttc"] = (factures.loc[idx, "montant_ttc"] * 1.1).round(3)
log.append(("factures", "montant_ttc", f"{len(idx)} lignes où ttc != ht + tva"))
# doublons de factures
dup = factures.sample(n=8, random_state=SEED)
factures = pd.concat([factures, dup], ignore_index=True)
log.append(("factures", "*", "8 lignes dupliquées exactement"))
# date_echeance < date_emission
idx = pick(factures, 0.005)
factures.loc[idx, "date_echeance"] = factures.loc[idx, "date_emission"]
log.append(("factures", "date_echeance", f"{len(idx)} échéances identiques à l'émission (suspect)"))

# --- encaissements
encaissements["date_encaissement"] = encaissements["date_encaissement"].astype(str)
encaissements["montant"] = encaissements["montant"].astype(object)
idx = pick(encaissements, 0.08)
encaissements.loc[idx, "date_encaissement"] = encaissements.loc[idx, "date_encaissement"].map(
    lambda s: pd.to_datetime(s).strftime("%d/%m/%Y"))
log.append(("encaissements", "date_encaissement", f"{len(idx)} dates au format JJ/MM/AAAA"))
idx = pick(encaissements, 0.03)
encaissements.loc[idx, "montant"] = encaissements.loc[idx, "montant"].map(
    lambda v: f"{v:.3f}".replace(".", ","))
log.append(("encaissements", "montant", f"{len(idx)} montants avec virgule décimale (texte)"))
idx = pick(encaissements, 0.012); encaissements.loc[idx, "banque_id"] = None
log.append(("encaissements", "banque_id", f"{len(idx)} valeurs manquantes"))
idx = pick(encaissements, 0.03); encaissements.loc[idx, "mode_paiement"] = None
log.append(("encaissements", "mode_paiement", f"{len(idx)} valeurs manquantes"))
idx = pick(encaissements, 0.06)
encaissements["mode_paiement"] = encaissements["mode_paiement"].astype(object)
encaissements.loc[idx, "mode_paiement"] = encaissements.loc[idx, "mode_paiement"].map(
    lambda v: v.lower() if isinstance(v, str) else v)
log.append(("encaissements", "mode_paiement", f"{len(idx)} valeurs en minuscules"))
idx = encaissements.sample(n=5, random_state=SEED + 1).index
encaissements.loc[idx, "montant"] = [-1500.0, -230.5, 0, 0, 98765432.1]
log.append(("encaissements", "montant", "5 aberrations (montants négatifs, nuls, ou 98M)"))
idx = pick(encaissements, 0.005)
encaissements.loc[idx, "facture_id"] = 999000 + np.arange(len(idx))
log.append(("encaissements", "facture_id", f"{len(idx)} références à des factures inexistantes (orphelins)"))
dup = encaissements.sample(n=12, random_state=SEED)
encaissements = pd.concat([encaissements, dup], ignore_index=True)
log.append(("encaissements", "*", "12 lignes dupliquées exactement"))

# ---------------------------------------------------------------- export
for name, df in [("banques", banques), ("clients", clients),
                 ("factures", factures), ("encaissements", encaissements)]:
    df.to_csv(OUT / f"{name}.csv", index=False, encoding="utf-8")
    print(f"{name:15s} {len(df):6d} lignes")

with open(OUT.parent / "ANOMALIES_CORRIGE.md", "w", encoding="utf-8") as fh:
    fh.write("# Anomalies volontairement injectées (corrigé pour l'encadrant)\n\n")
    fh.write("| Table | Colonne | Anomalie |\n|---|---|---|\n")
    for t, c, a in log:
        fh.write(f"| {t} | {c} | {a} |\n")
print("OK ->", OUT.resolve())
