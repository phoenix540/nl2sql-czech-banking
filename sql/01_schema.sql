-- Czech Financial Dataset. WARNING: this script drops the legacy demo schema.
DROP VIEW IF EXISTS v_district_summary CASCADE;
DROP VIEW IF EXISTS v_client_accounts CASCADE;
DROP VIEW IF EXISTS v_loan_summary CASCADE;
DROP VIEW IF EXISTS v_transactions_monthly CASCADE;
DROP VIEW IF EXISTS v_account_activity CASCADE;
DROP TABLE IF EXISTS etl_rejects CASCADE;
DROP TABLE IF EXISTS trans CASCADE;
DROP TABLE IF EXISTS bank_order CASCADE;
DROP TABLE IF EXISTS loan CASCADE;
DROP TABLE IF EXISTS card CASCADE;
DROP TABLE IF EXISTS disp CASCADE;
DROP TABLE IF EXISTS account CASCADE;
DROP TABLE IF EXISTS client CASCADE;
DROP TABLE IF EXISTS district CASCADE;
-- Legacy tables are removed during the migration so old views cannot linger.
DROP TABLE IF EXISTS encaissements CASCADE;
DROP TABLE IF EXISTS factures CASCADE;
DROP TABLE IF EXISTS clients CASCADE;
DROP TABLE IF EXISTS banques CASCADE;

CREATE TABLE district (
  "A1" INTEGER PRIMARY KEY,
  "A2" TEXT, "A3" TEXT, "A4" BIGINT, "A5" BIGINT, "A6" BIGINT,
  "A7" INTEGER, "A8" INTEGER, "A9" INTEGER, "A10" NUMERIC(8,2),
  "A11" BIGINT, "A12" NUMERIC(8,2), "A13" NUMERIC(8,2),
  "A14" BIGINT, "A15" BIGINT, "A16" BIGINT
);
CREATE TABLE client (
  client_id INTEGER PRIMARY KEY,
  birth_number TEXT,
  district_id INTEGER REFERENCES district("A1")
);
CREATE TABLE account (
  account_id INTEGER PRIMARY KEY,
  district_id INTEGER REFERENCES district("A1"),
  frequency TEXT,
  date DATE
);
CREATE TABLE disp (
  disp_id INTEGER PRIMARY KEY,
  client_id INTEGER NOT NULL REFERENCES client(client_id),
  account_id INTEGER NOT NULL REFERENCES account(account_id),
  type TEXT
);
CREATE TABLE card (
  card_id INTEGER PRIMARY KEY,
  disp_id INTEGER NOT NULL REFERENCES disp(disp_id),
  type TEXT,
  issued DATE
);
CREATE TABLE loan (
  loan_id INTEGER PRIMARY KEY,
  account_id INTEGER NOT NULL REFERENCES account(account_id),
  date DATE,
  amount NUMERIC(14,2),
  duration INTEGER,
  payments NUMERIC(14,2),
  status TEXT
);
CREATE TABLE bank_order (
  order_id INTEGER PRIMARY KEY,
  account_id INTEGER NOT NULL REFERENCES account(account_id),
  bank_to TEXT,
  account_to TEXT,
  amount NUMERIC(14,2),
  k_symbol TEXT
);
CREATE TABLE trans (
  trans_id INTEGER PRIMARY KEY,
  account_id INTEGER NOT NULL REFERENCES account(account_id),
  date DATE,
  type TEXT,
  operation TEXT,
  amount NUMERIC(14,2),
  balance NUMERIC(14,2),
  k_symbol TEXT,
  bank TEXT,
  account TEXT
);
CREATE TABLE etl_rejects (
  id BIGSERIAL PRIMARY KEY,
  table_name TEXT NOT NULL,
  reason TEXT NOT NULL,
  source_row TEXT NOT NULL,
  loaded_at TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX idx_client_district ON client(district_id);
CREATE INDEX idx_account_district ON account(district_id);
CREATE INDEX idx_disp_client ON disp(client_id);
CREATE INDEX idx_disp_account ON disp(account_id);
CREATE INDEX idx_loan_account ON loan(account_id);
CREATE INDEX idx_order_account ON bank_order(account_id);
CREATE INDEX idx_trans_account ON trans(account_id);
CREATE INDEX idx_trans_date ON trans(date);
CREATE INDEX idx_trans_account_date ON trans(account_id, date);
COMMENT ON TABLE district IS 'Czech district demographic and economic indicators. A1 is district ID; A2 district name; A3 region.';
COMMENT ON TABLE client IS 'Clients in the Czech banking dataset. birth_number is retained as text because it encodes a historical birth identifier.';
COMMENT ON TABLE account IS 'Bank accounts; date is the account creation date; frequency is the statement issuance frequency.';
COMMENT ON TABLE disp IS 'Disposition relationship linking clients to accounts. OWNER indicates owner; DISPONENT indicates an authorized user.';
COMMENT ON TABLE card IS 'Payment cards linked to account dispositions.';
COMMENT ON TABLE loan IS 'Loans linked to bank accounts. Original status codes are preserved: A good, B problem/defaulter, C running, D finished in the common dataset documentation.';
COMMENT ON TABLE bank_order IS 'Standing orders from order.csv. bank_order is used instead of reserved SQL keyword order.';
COMMENT ON TABLE trans IS 'Historical account transactions. amount and balance use the dataset original units; type and operation labels are retained in source language.';
COMMENT ON COLUMN trans.type IS 'Transaction direction in original labels, commonly PRIJEM (credit) or VYDAJ (debit).';
COMMENT ON COLUMN loan.status IS 'Original Czech dataset loan status code; do not interpret as a generic boolean.';
