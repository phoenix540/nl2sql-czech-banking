# Anomalies volontairement injectées (corrigé pour l'encadrant)

| Table | Colonne | Anomalie |
|---|---|---|
| clients | ville | 13 valeurs manquantes |
| clients | ville | 18 valeurs en MAJUSCULES (casse incohérente) |
| clients | raison_sociale | 11 valeurs avec espaces parasites |
| clients | secteur | 9 valeurs manquantes |
| clients | date_creation | 22 dates au format JJ/MM/AAAA (le reste en ISO) |
| factures | date_emission | 428 dates au format JJ/MM/AAAA |
| factures | date_echeance | 122 valeurs manquantes |
| factures | statut | ~611 libellés incohérents (payee/PAYEE/partiel...) |
| factures | montant_ttc | 61 lignes où ttc != ht + tva |
| factures | * | 8 lignes dupliquées exactement |
| factures | date_echeance | 31 échéances identiques à l'émission (suspect) |
| encaissements | date_encaissement | 480 dates au format JJ/MM/AAAA |
| encaissements | montant | 180 montants avec virgule décimale (texte) |
| encaissements | banque_id | 72 valeurs manquantes |
| encaissements | mode_paiement | 180 valeurs manquantes |
| encaissements | mode_paiement | 360 valeurs en minuscules |
| encaissements | montant | 5 aberrations (montants négatifs, nuls, ou 98M) |
| encaissements | facture_id | 30 références à des factures inexistantes (orphelins) |
| encaissements | * | 12 lignes dupliquées exactement |
