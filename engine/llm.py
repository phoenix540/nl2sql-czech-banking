"""Client Groq (API compatible OpenAI) avec nouvelles tentatives sur 429/5xx."""
from __future__ import annotations

import re
import time

import requests

from engine import settings

URL = "https://api.groq.com/openai/v1/chat/completions"
MODELS_URL = "https://api.groq.com/openai/v1/models"


class LLMError(RuntimeError):
    pass


class GroqLLM:
    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: int = 60):
        self.api_key = api_key or settings.groq_api_key()
        self.model = model or settings.groq_model()
        self.timeout = timeout
        if not self.api_key:
            raise LLMError("GROQ_API_KEY manquante : renseigne-la dans le fichier .env")

    def _payload(self, messages, with_effort=True) -> dict:
        payload = {"model": self.model, "messages": messages, "temperature": 0,
                   # les modèles à raisonnement dépensent des jetons en réflexion avant le SQL
                   "max_tokens": 4000}
        effort = settings.reasoning_effort()
        if with_effort and effort in ("low", "medium", "high") and self.model.startswith("openai/gpt-oss"):
            payload["reasoning_effort"] = effort
        return payload

    def chat(self, messages: list[dict]) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = self._payload(messages)
        last = ""
        for attempt in range(5):
            try:
                r = requests.post(URL, headers=headers, json=payload, timeout=self.timeout)
            except requests.RequestException as exc:
                last = f"réseau : {exc}"
                time.sleep(min(2 ** attempt, 15))
                continue
            if r.status_code == 200:
                choice = r.json()["choices"][0]
                content = choice["message"].get("content") or ""
                if not content.strip():
                    raise LLMError(f"Réponse vide du modèle {self.model} (finish_reason="
                                   f"{choice.get('finish_reason')}). Essaie un autre GROQ_MODEL.")
                return content
            last = f"HTTP {r.status_code} : {r.text[:300]}"
            if r.status_code == 400 and "reasoning" in r.text.lower() and "reasoning_effort" in payload:
                payload = self._payload(messages, with_effort=False)  # paramètre non supporté
                continue
            if r.status_code in (429, 500, 502, 503, 504):
                wait = float(r.headers.get("retry-after", 0) or 0) or min(2 ** attempt, 20)
                time.sleep(min(wait, 30))
                continue
            break  # 400/401/404... : inutile de réessayer
        raise LLMError(f"Appel Groq échoué ({last}). Vérifie la clé API et GROQ_MODEL.")


def list_models(api_key: str | None = None) -> list[str]:
    key = api_key or settings.groq_api_key()
    r = requests.get(MODELS_URL, headers={"Authorization": f"Bearer {key}"}, timeout=30)
    r.raise_for_status()
    return sorted(m["id"] for m in r.json().get("data", []))


_THINK = re.compile(r"<think>.*?</think>", re.S)
_FENCE = re.compile(r"```(?:sql)?\s*(.*?)```", re.S | re.I)


def extract_sql(content: str) -> str:
    """Isole le SQL d'une réponse (bloc ```sql ou texte brut)."""
    content = _THINK.sub("", content or "").strip()
    m = _FENCE.search(content)
    return (m.group(1) if m else content).strip()
