"""Configuration des chemins et de PostgreSQL pour le dataset bancaire tchèque."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
RAW_DIR = ROOT / "data" / "raw"  # conservé pour compatibilité avec les anciens scripts
CZECH_DIR = ROOT / "data" / "czech"
REPORTS_DIR = ROOT / "reports"
SQL_DIR = ROOT / "sql"

def db_url(read_only: bool = False) -> str:
    """URL SQLAlchemy. DATABASE_URL prioritaire pour les tests."""
    if os.getenv("DATABASE_URL") and not read_only:
        return os.environ["DATABASE_URL"]
    user = os.getenv("RO_USER" if read_only else "POSTGRES_USER", "nl2sql_admin")
    pwd = os.getenv("RO_PASSWORD" if read_only else "POSTGRES_PASSWORD", "")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "bns_demo")
    return f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}"
