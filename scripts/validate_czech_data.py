
from pathlib import Path
import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "data" / "czech"

def read(name):
    return pd.read_csv(
        DATA / f"{name}.csv",
        sep=";",
        dtype=str,
        keep_default_na=True
    )

district = read("district")
client = read("client")
account = read("account")
disp = read("disp")
card = read("card")
loan = read("loan")
orders = read("order")
trans = read("trans")

checks = [
    ("client.district_id -> district.A1",
     client, "district_id", district, "A1"),
    ("account.district_id -> district.A1",
     account, "district_id", district, "A1"),
    ("disp.client_id -> client.client_id",
     disp, "client_id", client, "client_id"),
    ("disp.account_id -> account.account_id",
     disp, "account_id", account, "account_id"),
    ("card.disp_id -> disp.disp_id",
     card, "disp_id", disp, "disp_id"),
    ("loan.account_id -> account.account_id",
     loan, "account_id", account, "account_id"),
    ("order.account_id -> account.account_id",
     orders, "account_id", account, "account_id"),
    ("trans.account_id -> account.account_id",
     trans, "account_id", account, "account_id"),
]

print("=== FOREIGN-KEY VALIDATION ===")
for label, child, fk, parent, pk in checks:
    child_values = child[fk].dropna()
    parent_values = set(parent[pk].dropna())
    missing = (~child_values.isin(parent_values)).sum()
    nulls = child[fk].isna().sum()
    print(f"{label}: unmatched={missing}, null={nulls}")

print("\n=== PRIMARY-KEY VALIDATION ===")
tables = [
    ("district", district, "A1"),
    ("client", client, "client_id"),
    ("account", account, "account_id"),
    ("disp", disp, "disp_id"),
    ("card", card, "card_id"),
    ("loan", loan, "loan_id"),
    ("order", orders, "order_id"),
    ("trans", trans, "trans_id"),
]

for name, df, pk in tables:
    print(
        f"{name}: null PK={df[pk].isna().sum()}, "
        f"duplicate PK={df[pk].duplicated().sum()}"
    )

print("\n=== DATE VALIDATION ===")
for name, column in [
    ("account", "date"),
    ("card", "issued"),
    ("loan", "date"),
    ("trans", "date"),
]:
    df = read(name)
    raw = df[column].astype("string").str.strip()
    compact = raw.str.slice(0, 6)
    parsed = pd.to_datetime(
        compact, format="%y%m%d", errors="coerce"
    )
    invalid = (raw.notna() & parsed.isna()).sum()
    print(
        f"{name}.{column}: invalid={invalid}, "
        f"min={parsed.min()}, max={parsed.max()}"
    )
