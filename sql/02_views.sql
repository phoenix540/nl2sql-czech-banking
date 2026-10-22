-- Analytic views exposed to NL-to-SQL (engine/schema.py exposes v_* relations).
DROP VIEW IF EXISTS v_district_summary CASCADE;
DROP VIEW IF EXISTS v_client_accounts CASCADE;
DROP VIEW IF EXISTS v_loan_summary CASCADE;
DROP VIEW IF EXISTS v_transactions_monthly CASCADE;
DROP VIEW IF EXISTS v_account_activity CASCADE;
DROP VIEW IF EXISTS v_accounts CASCADE;
DROP VIEW IF EXISTS v_clients CASCADE;
DROP VIEW IF EXISTS v_cards CASCADE;
DROP VIEW IF EXISTS v_loans CASCADE;
DROP VIEW IF EXISTS v_orders CASCADE;
DROP VIEW IF EXISTS v_transactions CASCADE;
DROP VIEW IF EXISTS v_dispositions CASCADE;
DROP VIEW IF EXISTS v_districts CASCADE;


-- Safe, documented business-facing views. The NL-to-SQL engine exposes v_* views only.
CREATE VIEW v_districts AS
SELECT "A1" AS district_id, "A2" AS district_name, "A3" AS region,
       "A4" AS population, "A10" AS unemployment_rate_95,
       "A12" AS unemployment_rate_96, "A13" AS entrepreneur_rate,
       "A15" AS crime_95, "A16" AS crime_96
FROM district;

CREATE VIEW v_clients AS
SELECT c.client_id, c.birth_number, c.district_id,
       d."A2" AS district_name, d."A3" AS region
FROM client c LEFT JOIN district d ON d."A1" = c.district_id;

CREATE VIEW v_accounts AS
SELECT a.account_id, a.district_id, d."A2" AS district_name, d."A3" AS region,
       a.frequency, a.date AS account_open_date
FROM account a LEFT JOIN district d ON d."A1" = a.district_id;

CREATE VIEW v_dispositions AS
SELECT dp.disp_id, dp.client_id, dp.account_id, dp.type AS disposition_type
FROM disp dp;

CREATE VIEW v_cards AS
SELECT c.card_id, c.disp_id, c.type AS card_type, c.issued
FROM card c;

CREATE VIEW v_loans AS
SELECT l.loan_id, l.account_id, l.date AS loan_date, l.amount, l.duration, l.payments, l.status,
       CASE l.status WHEN 'A' THEN 'good' WHEN 'B' THEN 'problematic/defaulter'
            WHEN 'C' THEN 'running' WHEN 'D' THEN 'finished' ELSE 'unknown' END AS status_description
FROM loan l;

CREATE VIEW v_orders AS
SELECT order_id, account_id, bank_to, account_to, amount, k_symbol FROM bank_order;

CREATE VIEW v_transactions AS
SELECT trans_id, account_id, date AS transaction_date, type AS transaction_type,
       operation, amount, balance, k_symbol, bank AS destination_bank,
       account AS destination_account
FROM trans;

CREATE VIEW v_account_activity AS
WITH tx AS (
  SELECT account_id, COUNT(*) AS transaction_count, SUM(amount) AS transaction_amount_sum,
         MAX(date) AS last_transaction_date
  FROM trans GROUP BY account_id
), dp AS (
  SELECT account_id, COUNT(DISTINCT client_id) AS linked_client_count
  FROM disp GROUP BY account_id
), ln AS (
  SELECT account_id, COUNT(*) AS loan_count FROM loan GROUP BY account_id
)
SELECT a.account_id, a.district_id, d."A2" AS district_name, d."A3" AS region,
       a.frequency, a.date AS account_open_date,
       COALESCE(tx.transaction_count, 0) AS transaction_count,
       COALESCE(tx.transaction_amount_sum, 0) AS transaction_amount_sum,
       tx.last_transaction_date,
       COALESCE(dp.linked_client_count, 0) AS linked_client_count,
       COALESCE(ln.loan_count, 0) AS loan_count
FROM account a
LEFT JOIN district d ON d."A1" = a.district_id
LEFT JOIN tx ON tx.account_id = a.account_id
LEFT JOIN dp ON dp.account_id = a.account_id
LEFT JOIN ln ON ln.account_id = a.account_id;

CREATE VIEW v_transactions_monthly AS
SELECT date_trunc('month', t.date)::date AS month,
       t.type, t.operation, t.k_symbol,
       COUNT(*) AS transaction_count,
       SUM(t.amount) AS amount_sum,
       AVG(t.amount) AS average_amount
FROM trans t
WHERE t.date IS NOT NULL
GROUP BY date_trunc('month', t.date)::date, t.type, t.operation, t.k_symbol;

CREATE VIEW v_loan_summary AS
SELECT l.loan_id, l.account_id, a.district_id, d."A2" AS district_name,
       l.date AS loan_date, l.amount, l.duration, l.payments, l.status,
       CASE l.status WHEN 'A' THEN 'good' WHEN 'B' THEN 'problematic/defaulter'
            WHEN 'C' THEN 'running' WHEN 'D' THEN 'finished' ELSE 'unknown' END AS status_description,
       CASE WHEN l.duration > 0 THEN l.amount / l.duration ELSE NULL END AS amount_per_duration_month
FROM loan l
JOIN account a ON a.account_id = l.account_id
LEFT JOIN district d ON d."A1" = a.district_id;

CREATE VIEW v_client_accounts AS
SELECT c.client_id, c.birth_number, c.district_id,
       d."A2" AS district_name, d."A3" AS region,
       dp.disp_id, dp.account_id, dp.type AS disposition_type,
       a.frequency, a.date AS account_open_date,
       COUNT(DISTINCT card.card_id) AS card_count
FROM client c
LEFT JOIN district d ON d."A1" = c.district_id
LEFT JOIN disp dp ON dp.client_id = c.client_id
LEFT JOIN account a ON a.account_id = dp.account_id
LEFT JOIN card ON card.disp_id = dp.disp_id
GROUP BY c.client_id, c.birth_number, c.district_id, d."A2", d."A3",
         dp.disp_id, dp.account_id, dp.type, a.frequency, a.date;

CREATE VIEW v_district_summary AS
WITH clients_by_district AS (
  SELECT district_id, COUNT(*) AS client_count FROM client GROUP BY district_id
), accounts_by_district AS (
  SELECT district_id, COUNT(*) AS account_count FROM account GROUP BY district_id
), loans_by_district AS (
  SELECT a.district_id, COUNT(l.loan_id) AS loan_count, COALESCE(SUM(l.amount), 0) AS loan_amount_sum
  FROM account a LEFT JOIN loan l ON l.account_id = a.account_id
  GROUP BY a.district_id
)
SELECT d."A1" AS district_id, d."A2" AS district_name, d."A3" AS region,
       COALESCE(c.client_count, 0) AS client_count,
       COALESCE(a.account_count, 0) AS account_count,
       COALESCE(l.loan_count, 0) AS loan_count,
       COALESCE(l.loan_amount_sum, 0) AS loan_amount_sum
FROM district d
LEFT JOIN clients_by_district c ON c.district_id = d."A1"
LEFT JOIN accounts_by_district a ON a.district_id = d."A1"
LEFT JOIN loans_by_district l ON l.district_id = d."A1";

COMMENT ON VIEW v_account_activity IS 'One row per bank account with transaction count, sum of transaction amounts, last transaction, linked clients and loan count. Transaction amount sum is the sum of raw transaction amounts, not a net cash-flow measure.';
COMMENT ON VIEW v_transactions_monthly IS 'Transaction counts and amount aggregates by calendar month and original transaction type, operation and symbol.';
COMMENT ON VIEW v_loan_summary IS 'Loan-level facts with account/district information and readable descriptions of original loan status codes.';
COMMENT ON VIEW v_client_accounts IS 'Client-to-account relationship rows, disposition type and count of linked cards.';
COMMENT ON VIEW v_district_summary IS 'District-level counts of clients, accounts and loans, with district name and region.';

COMMENT ON VIEW v_transactions IS 'Read-only business-facing transaction rows with transaction date, original type/operation, amount and resulting account balance.';
COMMENT ON VIEW v_loans IS 'Read-only loan rows with amount, duration, payment amount and original status code plus description.';
COMMENT ON VIEW v_cards IS 'Read-only card records by card type and issue date.';
COMMENT ON VIEW v_orders IS 'Read-only standing orders from the source order.csv.';
COMMENT ON VIEW v_clients IS 'Client records with district name and region. birth_number is a source identifier, not a name.';
COMMENT ON VIEW v_accounts IS 'Account records with district name, region, statement frequency and opening date.';
COMMENT ON VIEW v_districts IS 'District-level source indicators; indicator names are approximate interpretations of the original A-column documentation.';
COMMENT ON VIEW v_dispositions IS 'Relationships between clients and accounts, with OWNER or DISPONENT role.';
