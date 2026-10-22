
from pathlib import Path
import pandas as pd

DATA_DIR = Path("data/czech")

files = [
    "account.csv",
    "card.csv",
    "client.csv",
    "disp.csv",
    "district.csv",
    "loan.csv",
    "order.csv",
    "trans.csv",
]

for filename in files:
    path = DATA_DIR / filename

    if not path.exists():
        print(f"MISSING: {path}")
        continue

    df = pd.read_csv(path, sep=";", nrows=5)

    print(f"\n{'=' * 50}")
    print(f"File: {filename}")
    print(f"Columns: {list(df.columns)}")
    print(f"Sample rows: {len(df)}")
    print(df.head(2).to_string(index=False))
