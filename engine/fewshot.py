"""Exemples question -> SQL pour le Czech Financial Dataset."""
FEWSHOT = [
    ("Combien de comptes y a-t-il dans chaque district ?",
     "SELECT district_name, account_count FROM v_district_summary ORDER BY account_count DESC"),
    ("Quels sont les 10 comptes qui ont le plus de transactions ?",
     "SELECT account_id, transaction_count FROM v_account_activity ORDER BY transaction_count DESC LIMIT 10"),
    ("Combien de prêts y a-t-il par statut ?",
     "SELECT status_description, COUNT(*) AS nombre_prets FROM v_loans GROUP BY status_description ORDER BY nombre_prets DESC"),
    ("Quel est le montant total des prêts par district ?",
     "SELECT district_name, SUM(amount) AS montant_total_prets FROM v_loan_summary GROUP BY district_name ORDER BY montant_total_prets DESC"),
    ("Évolution mensuelle du nombre de transactions",
     "SELECT month, SUM(transaction_count) AS nombre_transactions FROM v_transactions_monthly GROUP BY month ORDER BY month"),
]
