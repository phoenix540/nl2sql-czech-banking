# Rapport de profilage des données brutes

## banques (10 lignes, 4 colonnes)

| Colonne | Type inféré | Nulls | Distincts | Exemples |
|---|---|---|---|---|
| banque_id | entier | 0 | 10 | 1, 2, 3 |
| nom_banque | texte | 0 | 10 | BIAT, STB, BNA |
| code_banque | entier | 0 | 10 | 08, 10, 03 |
| raison_sociale_banque | texte | 0 | 10 | Banque Internationale Arabe de Tunisie, Société Tunisienne de Banque, Banque Nationale Agricole |

**Problèmes détectés :**

- aucun

## clients (220 lignes, 6 colonnes)

| Colonne | Type inféré | Nulls | Distincts | Exemples |
|---|---|---|---|---|
| client_id | entier | 0 | 220 | 1, 2, 3 |
| raison_sociale | texte | 0 | 220 | Atlas Agro, Atlas Construction, Atlas Group |
| secteur | texte | 9 | 9 | Technologies, Services, Commerce |
| ville | texte | 13 | 17 | Gabès, Tunis, Monastir |
| segment | texte | 0 | 3 | TPE, PME, Grand compte |
| date_creation | date | 0 | 219 | 2019-09-23, 2019-08-17, 2024-01-22 |

**Problèmes détectés :**

- `raison_sociale` : 11 valeurs avec espaces parasites
- `secteur` : 9 valeurs manquantes (4.1%)
- `ville` : 13 valeurs manquantes (5.9%)
- `ville` : variantes d'un même libellé (ARIANA/Ariana ; BEN AROUS/Ben Arous ; KAIROUAN/Kairouan...)
- `date_creation` : formats de date mixtes (198 ISO / 22 JJ/MM/AAAA)

## encaissements (6,016 lignes, 7 colonnes)

| Colonne | Type inféré | Nulls | Distincts | Exemples |
|---|---|---|---|---|
| encaissement_id | entier | 0 | 6004 | 1, 2, 3 |
| facture_id | entier | 0 | 5239 | 1, 2, 3 |
| banque_id | entier | 84 | 10 | 6.0, 7.0, 3.0 |
| date_encaissement | date | 0 | 859 | 2025-05-10, 2025-05-11, 2025-05-23 |
| montant | décimal | 0 | 6001 | 9364.546, 5306.594, 1025.887 |
| mode_paiement | texte | 192 | 10 | Chèque, Traite, Virement |
| reference | texte | 0 | 6004 | REF2505000001, REF2505000002, REF2505000003 |

**Problèmes détectés :**

- 12 lignes entièrement dupliquées
- 12 doublons sur la clé `encaissement_id`
- `banque_id` : 84 valeurs manquantes (1.4%)
- `date_encaissement` : formats de date mixtes (5524 ISO / 492 JJ/MM/AAAA)
- `montant` : 191 nombres avec virgule décimale (colonne lue comme texte)
- `montant` : 4 valeurs <= 0
- `montant` : 1 valeurs aberrantes (> 20 x P99 = 3,094,441), max = 98,765,432
- `mode_paiement` : 192 valeurs manquantes (3.2%)
- `mode_paiement` : variantes d'un même libellé (Chèque/chèque ; Espèces/espèces ; Prélèvement/prélèvement...)

## factures (6,118 lignes, 8 colonnes)

| Colonne | Type inféré | Nulls | Distincts | Exemples |
|---|---|---|---|---|
| facture_id | entier | 0 | 6110 | 1, 2, 3 |
| client_id | entier | 0 | 220 | 2, 3, 4 |
| date_emission | date | 0 | 874 | 2025-04-21, 2025-04-24, 2025-04-04 |
| date_echeance | date | 127 | 609 | 2025-05-21, 2025-06-08, 2025-05-19 |
| montant_ht | décimal | 0 | 6108 | 12328.689, 2020.319, 778.843 |
| montant_tva | décimal | 0 | 6103 | 2342.451, 383.861, 147.98 |
| montant_ttc | décimal | 0 | 6108 | 14671.14, 2404.18, 926.823 |
| statut | texte | 0 | 11 | Payée, Partiellement payée, partiel |

**Problèmes détectés :**

- 7 lignes entièrement dupliquées
- 8 doublons sur la clé `facture_id`
- `date_emission` : formats de date mixtes (5682 ISO / 436 JJ/MM/AAAA)
- `date_echeance` : 127 valeurs manquantes (2.1%)
- `date_echeance` : formats de date mixtes (5979 ISO / 12 JJ/MM/AAAA)
- `statut` : variantes d'un même libellé (IMPAYEE/Impayée/impayee ; PAYEE/Payee/Payée/payee...)

## Intégrité référentielle

- `encaissements.facture_id` -> `factures.facture_id` : 42 références orphelines
- `encaissements.banque_id` -> `banques.banque_id` : intégrité OK
- `factures.client_id` -> `clients.client_id` : intégrité OK