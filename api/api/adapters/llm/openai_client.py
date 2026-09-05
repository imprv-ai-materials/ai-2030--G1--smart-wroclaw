"""Thin OpenAI wrapper.

Two entry points the agents need: free-form `complete_text` (the assistant's
prose answer) and `complete_structured` (the triage agent's typed verdict). The
client is intentionally minimal — model choice + retries live here, prompt
construction lives in each agent. Callers that run without a configured key
should branch on `is_configured` and fall back to an offline heuristic so the
whole stack stays runnable in local dev without credentials.
"""

import json
from typing import Type, TypeVar

from loguru import logger
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

T = TypeVar("T", bound=BaseModel)


class OpenAIClient:
    def __init__(self, api_key: str | None, default_model_name: str = "gpt-5.4") -> None:
        self._api_key = api_key
        self._default_model_name = default_model_name
        self._client = None
        if api_key:
            # Imported lazily so the package imports cleanly without the SDK's
            # transitive deps present in a minimal migrations image.
            from openai import OpenAI

            self._client = OpenAI(api_key=api_key)

    @property
    def is_configured(self) -> bool:
        return self._client is not None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def complete_text(self, system: str, user: str, model: str | None = None) -> str:
        if self._client is None:
            raise RuntimeError("OpenAIClient not configured (missing api key)")
        resp = self._client.chat.completions.create(
            model=model or self._default_model_name,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return (resp.choices[0].message.content or "").strip()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def complete_structured(self, system: str, user: str, schema: Type[T], model: str | None = None) -> T:
        """Force a JSON object matching `schema` and validate it. Uses the
        `response_format=json_object` mode for broad SDK compatibility."""
        if self._client is None:
            raise RuntimeError("OpenAIClient not configured (missing api key)")
        schema_hint = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        resp = self._client.chat.completions.create(
            model=model or self._default_model_name,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": f"{user}\n\nOdpowiedz WYŁĄCZNIE obiektem JSON zgodnym ze schematem:\n{schema_hint}",
                },
            ],
        )
        raw = resp.choices[0].message.content or "{}"
        try:
            return schema.model_validate_json(raw)
        except Exception:
            logger.exception("failed to parse structured LLM output: {}", raw)
            raise
