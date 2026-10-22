"""Paramètres du moteur, lus dans .env (chargé par etl.config)."""
import os

import etl.config  # noqa: F401  (charge le fichier .env)


def groq_api_key() -> str:
    return os.getenv("GROQ_API_KEY", "").strip()


def groq_model() -> str:
    return os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()


def exposed_prefix() -> str:
    return os.getenv("EXPOSED_PREFIX", "v_")


def max_rows() -> int:
    return int(os.getenv("MAX_ROWS", "1000"))


def statement_timeout_s() -> int:
    return int(os.getenv("STATEMENT_TIMEOUT_S", "10"))


def max_retries() -> int:
    return int(os.getenv("MAX_RETRIES", "2"))


def reasoning_effort() -> str:
    """low | medium | high pour les modèles openai/gpt-oss ; vide pour désactiver."""
    return os.getenv("GROQ_REASONING_EFFORT", "low").strip().lower()
