# Évaluation NL-to-SQL

Modèle : `openai/gpt-oss-120b`  |  Précision : **19/20**

| Question | Verdict | Corrections | Temps (s) |
|---|---|---|---|
| Montant total encaissé par banque ce mois-ci | exact | 0 | 1.1 |
| Montant total encaissé le mois dernier | exact | 0 | 2.7 |
| Top 5 des clients par chiffre d'affaires | exact | 0 | 0.8 |
| Taux de recouvrement par secteur | exact | 0 | 0.6 |
| Combien de factures ont plus de 90 jours de retard ? | exact | 0 | 1.3 |
| Chiffre d'affaires TTC par mois | exact | 0 | 11.5 |
| Montant encaissé par mode de paiement | exact | 0 | 14.1 |
| Nombre d'encaissements par banque | exact | 0 | 1.8 |
| Quelle banque a encaissé le plus en 2026 ? | colonnes en plus | 1 | 1.6 |
| Total du reste à payer par segment de client | exact | 0 | 3.1 |
| Combien de clients par ville ? | exact | 0 | 3.0 |
| Les 10 clients avec le plus gros reste à payer | exact | 0 | 13.1 |
| Montant total encaissé par ville en 2026 | exact | 0 | 1.2 |
| Chiffre d'affaires HT total en 2026 | exact | 0 | 13.1 |
| Nombre de factures par statut | exact | 0 | 14.3 |
| Montant moyen d'un encaissement par banque | exact | 0 | 0.9 |
| Évolution mensuelle du total encaissé | exact | 0 | 0.8 |
| Quel secteur a le plus faible taux de recouvrement ? | colonnes en plus | 0 | 2.2 |
| Total encaissé par les clients Grand compte | faux | 0 | 2.6 |
| Liste des factures impayées de plus de 100000 TND | colonnes en plus | 0 | 1.2 |

## Échecs détaillés

**Total encaissé par les clients Grand compte**
```sql
SELECT client,
       SUM(montant) AS montant_total
FROM v_encaissements_detail
WHERE segment = 'Grand compte'
GROUP BY client
ORDER BY montant_total DESC
```
Erreur : None
