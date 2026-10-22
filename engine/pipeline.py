"""Chaîne complète : question -> prompt -> LLM -> validation -> exécution -> (retry)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import pandas as pd

from engine import executor, schema, settings
from engine.llm import GroqLLM, extract_sql
from engine.prompt import IMPOSSIBLE_TAG, build_system_prompt
from engine.validator import validate


@dataclass
class Answer:
    question: str
    sql: str = ""
    df: pd.DataFrame | None = None
    error: str | None = None
    impossible: str | None = None
    truncated: bool = False
    attempts: list = field(default_factory=list)  # [{"sql":..., "error":...}]
    seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return self.df is not None and self.error is None


class NL2SQL:
    def __init__(self, llm, engine, relations, blocked, max_retries: int | None = None):
        self.llm = llm
        self.engine = engine
        self.blocked = set(blocked)
        self.relations = relations
        self.schema_text = schema.render(relations)
        self.max_retries = settings.max_retries() if max_retries is None else max_retries

    @classmethod
    def from_env(cls, llm=None):
        eng, mode = executor.make_engine()
        rels, blocked = schema.introspect(eng, settings.exposed_prefix())
        if not rels:
            raise RuntimeError("Aucune table/vue trouvée : lance d'abord python -m etl.run")
        inst = cls(llm or GroqLLM(), eng, rels, blocked)
        inst.security_mode = mode
        return inst

    def ask(self, question: str) -> Answer:
        t0 = time.time()
        ans = Answer(question=question)
        messages = [{"role": "system", "content": build_system_prompt(self.schema_text)},
                    {"role": "user", "content": question}]
        for attempt in range(self.max_retries + 1):
            raw = self.llm.chat(messages)
            sql = extract_sql(raw)
            if sql.lstrip().upper().startswith(IMPOSSIBLE_TAG.upper()):
                ans.impossible = sql.split(":", 1)[1].strip()
                break
            ans.sql = sql
            v = validate(sql, self.blocked)
            err = None if v.ok else v.error
            if v.ok:
                res = executor.run_query(self.engine, v.sql)
                if res.error is None:
                    ans.df, ans.truncated, ans.error = res.df, res.truncated, None
                    ans.attempts.append({"sql": sql, "error": None})
                    break
                err = res.error
            ans.attempts.append({"sql": sql, "error": err})
            ans.error = err
            messages += [{"role": "assistant", "content": f"```sql\n{sql}\n```"},
                         {"role": "user", "content":
                          f"Cette requête a échoué : {err}\nCorrige-la et renvoie uniquement le SQL corrigé."}]
        ans.seconds = time.time() - t0
        return ans
