"""LLM access: Gemini or Groq (picked by LLM_PROVIDER), plus a fake for tests.

All of them expose the same two methods, so the agent does not care which it gets:
- json(prompt)  -> dict   (the model must answer with JSON)
- text(prompt)  -> str
Each also counts its calls in `.calls` and names itself in `.name`.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Callable

from dotenv import load_dotenv

DEFAULTS = {"gemini": "gemini-3.5-flash-lite", "groq": "llama-3.3-70b-versatile"}
RETRYABLE_CODES = {429, 500, 502, 503}  # rate limit, server error, overloaded


class LLMError(RuntimeError):
    pass


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    # Models sometimes wrap JSON in ```json fences; strip them.
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
    return json.loads(raw)


class _RetryingLLM:
    """Shared retry-with-backoff loop. Subclasses implement `_call`."""

    name = "base"

    def __init__(self, max_retries: int = 5, base_delay: float = 2.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.calls = 0  # every attempt counts, retries included (it all uses quota)

    def _call(self, prompt: str, as_json: bool) -> str:  # pragma: no cover
        raise NotImplementedError

    def _status(self, exc: Exception) -> int | None:  # pragma: no cover
        raise NotImplementedError

    def _generate(self, prompt: str, as_json: bool) -> str:
        for attempt in range(self.max_retries + 1):
            self.calls += 1
            try:
                return self._call(prompt, as_json)
            except Exception as e:
                code = self._status(e)
                # Retry rate limits / server errors, and network errors (no HTTP code at all).
                retryable = code in RETRYABLE_CODES or code is None
                if not retryable or attempt == self.max_retries:
                    raise LLMError(f"{self.name} error {code}: {e}") from e
                time.sleep(self.base_delay * (2 ** attempt))  # 2s, 4s, 8s, 16s, 32s
        raise LLMError("unreachable")

    def json(self, prompt: str) -> dict:
        return _parse_json(self._generate(prompt, as_json=True))

    def text(self, prompt: str) -> str:
        return self._generate(prompt, as_json=False).strip()


class GeminiLLM(_RetryingLLM):
    def __init__(self, model: str | None = None, api_key: str | None = None, **kw):
        super().__init__(**kw)
        from google import genai

        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise LLMError("GEMINI_API_KEY is not set (see .env.example).")
        self.model = model or os.getenv("GEMINI_MODEL") or DEFAULTS["gemini"]
        self.name = f"gemini:{self.model}"
        self.client = genai.Client(api_key=key)

    def _call(self, prompt: str, as_json: bool) -> str:
        from google.genai import types

        config = types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json" if as_json else "text/plain",
        )
        resp = self.client.models.generate_content(model=self.model, contents=prompt, config=config)
        return resp.text or ""

    def _status(self, exc: Exception) -> int | None:
        return getattr(exc, "code", None)


class GroqLLM(_RetryingLLM):
    def __init__(self, model: str | None = None, api_key: str | None = None, **kw):
        super().__init__(**kw)
        from groq import Groq

        key = api_key or os.getenv("GROQ_API_KEY")
        if not key:
            raise LLMError("GROQ_API_KEY is not set (see .env.example).")
        self.model = model or os.getenv("GROQ_MODEL") or DEFAULTS["groq"]
        self.name = f"groq:{self.model}"
        self.client = Groq(api_key=key, max_retries=0)  # we do our own retries

    def _call(self, prompt: str, as_json: bool) -> str:
        kwargs = {"response_format": {"type": "json_object"}} if as_json else {}
        resp = self.client.chat.completions.create(
            model=self.model, temperature=0,
            messages=[{"role": "user", "content": prompt}], **kwargs)
        return resp.choices[0].message.content or ""

    def _status(self, exc: Exception) -> int | None:
        return getattr(exc, "status_code", None)


def make_llm(provider: str | None = None) -> _RetryingLLM:
    """Build the LLM named by LLM_PROVIDER (default: gemini)."""
    load_dotenv()
    provider = (provider or os.getenv("LLM_PROVIDER") or "gemini").strip().lower()
    if provider == "gemini":
        return GeminiLLM()
    if provider == "groq":
        return GroqLLM()
    raise LLMError(f"Unknown LLM_PROVIDER '{provider}' (use gemini or groq).")


class FakeLLM:
    """Test double. `json_fn` and `text_fn` receive the prompt and return the
    answer, so a test can script exactly what the 'model' says."""

    name = "fake"

    def __init__(self, json_fn: Callable[[str], dict], text_fn: Callable[[str], str] | None = None):
        self.json_fn = json_fn
        self.text_fn = text_fn or (lambda prompt: "FAKE REPLY")
        self.calls = 0
        self.prompts: list[str] = []

    def json(self, prompt: str) -> dict:
        self.calls += 1
        self.prompts.append(prompt)
        return self.json_fn(prompt)

    def text(self, prompt: str) -> str:
        self.calls += 1
        self.prompts.append(prompt)
        return self.text_fn(prompt)
