"""LLM adapter (SPEC section 6): `complete()` and `complete_json()` over Groq or Gemini.

Strategy/adapter pattern: callers never know which provider answers. Every failure, from a
timeout to a malformed body, becomes `LLMError`, so callers handle exactly one exception type.
LLM output is untrusted: `complete_json` parses defensively and never returns a non-dict.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

# Replaced in tests: a client on httpx.MockTransport, and a sleep that only records.
_sleep: Callable[[float], None] = time.sleep


def _http_client() -> httpx.Client:
    return httpx.Client(timeout=settings.llm_timeout_seconds)


class LLMError(Exception):
    """Any LLM failure: not configured, network, HTTP error, refusal or unusable output."""


# --- HTTP with retries ----------------------------------------------------------------------


def _retry_delay(attempt: int, response: httpx.Response | None) -> float:
    """Exponential backoff (1 s, 2 s, 4 s), or the server's Retry-After if it sent one."""
    if response is not None:
        retry_after = response.headers.get("retry-after", "")
        try:
            return min(float(retry_after), settings.llm_max_retry_after_seconds)
        except ValueError:
            pass  # missing, or an HTTP date: fall back to backoff
    return float(settings.llm_backoff_base_seconds * 2**attempt)


def _post_json(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    """POST and return the JSON body. Retries 429, 5xx and network errors; raises LLMError."""
    with _http_client() as client:
        for attempt in range(settings.llm_max_retries + 1):
            response: httpx.Response | None = None
            try:
                response = client.post(url, headers=headers, json=payload)
            except httpx.TransportError as exc:
                problem = f"network error: {type(exc).__name__}"
            else:
                if response.status_code == 200:
                    try:
                        body = response.json()
                    except ValueError as exc:
                        raise LLMError("LLM returned a non-JSON body") from exc
                    if not isinstance(body, dict):
                        raise LLMError("LLM returned an unexpected JSON shape")
                    return body
                if response.status_code not in RETRYABLE_STATUS:
                    # 400, 401, 403, 404: retrying won't help. Don't echo the body (may hold the prompt).
                    raise LLMError(f"LLM request rejected with HTTP {response.status_code}")
                problem = f"HTTP {response.status_code}"

            if attempt == settings.llm_max_retries:
                raise LLMError(f"LLM unavailable after {attempt + 1} attempts ({problem})")
            delay = _retry_delay(attempt, response)
            logger.warning("LLM %s, retrying in %.1f s", problem, delay)
            _sleep(delay)
    raise LLMError("unreachable")  # pragma: no cover


# --- Providers ------------------------------------------------------------------------------


def _groq(system: str, user: str, temperature: float, max_tokens: int, json_mode: bool) -> str:
    if settings.groq_api_key is None or not settings.groq_model:
        raise LLMError("Groq is not configured")
    # Only parameters every Groq chat model accepts (SPEC section 9 #6).
    payload: dict[str, Any] = {
        "model": settings.groq_model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": temperature,
        "max_completion_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    headers = {"Authorization": f"Bearer {settings.groq_api_key.get_secret_value()}"}
    body = _post_json(GROQ_URL, headers, payload)
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError("Groq response had no message content") from exc
    if not isinstance(content, str) or not content.strip():
        raise LLMError("Groq returned empty content")
    return content


def _gemini(system: str, user: str, temperature: float, max_tokens: int, json_mode: bool) -> str:
    if settings.gemini_api_key is None or not settings.gemini_model:
        raise LLMError("Gemini is not configured")
    generation: dict[str, Any] = {"temperature": temperature, "maxOutputTokens": max_tokens}
    if json_mode:
        generation["responseMimeType"] = "application/json"
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": generation,
    }
    # Key in a header, not in the URL: URLs end up in proxy and access logs.
    headers = {"x-goog-api-key": settings.gemini_api_key.get_secret_value()}
    body = _post_json(GEMINI_URL.format(model=settings.gemini_model), headers, payload)
    try:
        parts = body["candidates"][0]["content"]["parts"]
        content = "".join(str(part.get("text", "")) for part in parts)
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise LLMError("Gemini response had no content (possibly blocked)") from exc
    if not content.strip():
        raise LLMError("Gemini returned empty content")
    return content


_PROVIDERS = {"groq": _groq, "gemini": _gemini}


# --- Public interface -----------------------------------------------------------------------


def complete(
    user: str, system: str, temperature: float = 0.2, max_tokens: int = 600, *, json_mode: bool = False
) -> str:
    """One chat completion as plain text. Raises LLMError on any failure."""
    provider = _PROVIDERS.get(settings.llm_provider)
    if provider is None:
        raise LLMError("no LLM provider configured")
    return provider(system, user, temperature, max_tokens, json_mode).strip()


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def parse_json_object(raw: str) -> dict[str, Any]:
    """Parse LLM output as a JSON object: strip ``` fences, try json.loads, then the outermost {...}."""
    cleaned = _FENCE.sub("", raw.strip())
    candidates = [cleaned]
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end > start:
        candidates.append(cleaned[start : end + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise LLMError("LLM output was not a JSON object")


def complete_json(
    user: str, system: str, temperature: float = 0.2, max_tokens: int = 900
) -> dict[str, Any]:
    """A completion parsed as a JSON object. Raises LLMError if it can't be parsed."""
    return parse_json_object(complete(user, system, temperature, max_tokens, json_mode=True))
