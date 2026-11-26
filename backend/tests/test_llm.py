"""LLM adapter: retries, error mapping, provider payloads and defensive JSON parsing. No network."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from app import llm
from app.config import Settings, settings
from app.llm import LLMError

Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    recorded: list[float] = []
    monkeypatch.setattr(llm, "_sleep", recorded.append)
    return recorded


@pytest.fixture
def groq(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[[Handler], list[httpx.Request]]]:
    """Configure Groq and route its HTTP calls to a fake handler. Returns the seen requests."""
    monkeypatch.setattr(settings, "llm_provider", "groq")
    monkeypatch.setattr(settings, "groq_api_key", SecretStr("gsk_test_key"))
    monkeypatch.setattr(settings, "groq_model", "test-model")

    def install(handler: Handler) -> list[httpx.Request]:
        seen: list[httpx.Request] = []

        def recording(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return handler(request)

        monkeypatch.setattr(
            llm, "_http_client", lambda: httpx.Client(transport=httpx.MockTransport(recording))
        )
        return seen

    yield install


def groq_ok(content: str = "Refunds take 5 days [1].") -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


# --- Retries --------------------------------------------------------------------------------


def test_success_on_first_try(groq, sleeps: list[float]) -> None:
    seen = groq(lambda _r: groq_ok())
    assert llm.complete("q", "sys") == "Refunds take 5 days [1]."
    assert len(seen) == 1 and sleeps == []


def test_retries_429_and_5xx_with_exponential_backoff(groq, sleeps: list[float]) -> None:
    responses = iter([httpx.Response(429), httpx.Response(503), httpx.Response(500), groq_ok()])
    seen = groq(lambda _r: next(responses))
    assert llm.complete("q", "sys") == "Refunds take 5 days [1]."
    assert len(seen) == 4
    assert sleeps == [1.0, 2.0, 4.0]


def test_gives_up_after_three_retries(groq, sleeps: list[float]) -> None:
    seen = groq(lambda _r: httpx.Response(503))
    with pytest.raises(LLMError, match="after 4 attempts"):
        llm.complete("q", "sys")
    assert len(seen) == 4 and sleeps == [1.0, 2.0, 4.0]


def test_respects_retry_after_but_caps_it(groq, sleeps: list[float]) -> None:
    responses = iter(
        [
            httpx.Response(429, headers={"retry-after": "3"}),
            httpx.Response(429, headers={"retry-after": "9999"}),
            groq_ok(),
        ]
    )
    groq(lambda _r: next(responses))
    llm.complete("q", "sys")
    assert sleeps == [3.0, settings.llm_max_retry_after_seconds]


def test_network_errors_are_retried(groq, sleeps: list[float]) -> None:
    calls = {"n": 0}

    def flaky(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectTimeout("timed out", request=request)
        return groq_ok()

    groq(flaky)
    assert llm.complete("q", "sys").startswith("Refunds")
    assert sleeps == [1.0]


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_client_errors_are_not_retried(groq, sleeps: list[float], status: int) -> None:
    seen = groq(lambda _r: httpx.Response(status, text="secret prompt echoed back"))
    with pytest.raises(LLMError) as info:
        llm.complete("q", "sys")
    assert len(seen) == 1 and sleeps == []
    assert "secret prompt" not in str(info.value)  # response bodies are never echoed


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="<html>not json</html>"),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, json={"choices": [{"message": {"content": "   "}}]}),
    ],
)
def test_malformed_success_bodies_become_llm_error(groq, sleeps, response: httpx.Response) -> None:
    groq(lambda _r: response)
    with pytest.raises(LLMError):
        llm.complete("q", "sys")


def test_groq_reply_cut_off_by_the_token_budget_is_an_error(groq, sleeps) -> None:
    """HTTP 200 with finish_reason=length: the text is half an answer, so callers must fall back."""
    cut = {"choices": [{"message": {"content": "In November the team handled 256 questions, with"}, "finish_reason": "length"}]}
    seen = groq(lambda _r: httpx.Response(200, json=cut))
    with pytest.raises(LLMError, match="cut off"):
        llm.complete("q", "sys")
    assert len(seen) == 1 and sleeps == []  # not retried: the same budget would be cut again


def test_cut_off_topic_name_falls_back_to_keywords(groq, sleeps) -> None:
    """End to end: a truncated reply never becomes a stored topic name."""
    from app.analytics.clustering import name_topic

    cut = {"choices": [{"message": {"content": "Card payment"}, "finish_reason": "length"}]}
    groq(lambda _r: httpx.Response(200, json=cut))
    assert name_topic(["card", "declined", "bank"], ["my card was declined"]) == "Card declined bank"


def test_gemini_reply_cut_off_by_the_token_budget_is_an_error(monkeypatch: pytest.MonkeyPatch, sleeps) -> None:
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    monkeypatch.setattr(settings, "gemini_api_key", SecretStr("AIza_test"))
    monkeypatch.setattr(settings, "gemini_model", "gemini-test")
    cut = {"candidates": [{"content": {"parts": [{"text": "In November"}]}, "finishReason": "MAX_TOKENS"}]}
    monkeypatch.setattr(
        llm, "_http_client", lambda: httpx.Client(transport=httpx.MockTransport(lambda _r: httpx.Response(200, json=cut)))
    )
    with pytest.raises(LLMError, match="cut off"):
        llm.complete("q", "sys")


# --- Client-side pacing ---------------------------------------------------------------------


def test_requests_are_spaced_by_the_minimum_interval(groq, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fake clock: sleeping advances it, so the test is instant and deterministic."""
    now = [100.0]
    waits: list[float] = []

    def fake_sleep(seconds: float) -> None:
        waits.append(round(seconds, 3))
        now[0] += seconds

    monkeypatch.setattr(llm, "_clock", lambda: now[0])
    monkeypatch.setattr(llm, "_sleep", fake_sleep)
    monkeypatch.setattr(llm, "_last_request_at", None)
    monkeypatch.setattr(settings, "llm_min_interval_seconds", 2.0)
    groq(lambda _r: groq_ok())

    llm.complete("q", "sys")  # first request: nothing to wait for
    now[0] += 0.5  # the caller does 0.5 s of other work
    llm.complete("q", "sys")  # waits the remaining 1.5 s
    now[0] += 5.0  # a long pause
    llm.complete("q", "sys")  # already spaced out: no wait
    assert waits == [1.5]


def test_retries_are_paced_too(groq, monkeypatch: pytest.MonkeyPatch) -> None:
    now = [0.0]
    waits: list[float] = []
    monkeypatch.setattr(llm, "_clock", lambda: now[0])
    monkeypatch.setattr(llm, "_sleep", lambda s: (waits.append(s), now.__setitem__(0, now[0] + s)))
    monkeypatch.setattr(llm, "_last_request_at", None)
    monkeypatch.setattr(settings, "llm_min_interval_seconds", 2.0)
    monkeypatch.setattr(settings, "llm_backoff_base_seconds", 0.5)
    responses = iter([httpx.Response(429), groq_ok()])
    groq(lambda _r: next(responses))

    llm.complete("q", "sys")
    assert waits == [0.5, 1.5]  # backoff 0.5 s, then pacing tops it up to the 2 s gap


# --- Provider payloads ----------------------------------------------------------------------


def test_groq_payload_only_has_supported_parameters(groq, sleeps) -> None:
    seen = groq(lambda _r: groq_ok('{"a": 1}'))
    llm.complete_json("q", "sys")
    body = json.loads(seen[0].content)
    assert set(body) == {"model", "messages", "temperature", "max_completion_tokens", "response_format"}
    assert "reasoning_effort" not in body  # the reference sent it to models that reject it
    assert seen[0].headers["authorization"] == "Bearer gsk_test_key"


def test_gemini_sends_key_in_header_not_url(monkeypatch: pytest.MonkeyPatch, sleeps) -> None:
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    monkeypatch.setattr(settings, "gemini_api_key", SecretStr("AIza_test"))
    monkeypatch.setattr(settings, "gemini_model", "gemini-test")
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "Hi"}]}}]})

    monkeypatch.setattr(llm, "_http_client", lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    assert llm.complete("q", "sys") == "Hi"
    assert "AIza_test" not in str(seen[0].url)
    assert seen[0].headers["x-goog-api-key"] == "AIza_test"


def test_no_provider_raises_llm_error() -> None:
    with pytest.raises(LLMError, match="no LLM provider"):
        llm.complete("q", "sys")  # tests run with LLM_PROVIDER=none


def test_chosen_provider_without_key_fails_at_startup() -> None:
    with pytest.raises(ValidationError, match="GROQ_API_KEY"):
        Settings(_env_file=None, backend_jwt_secret="x" * 32, llm_provider="groq")


def test_api_key_is_hidden_in_repr() -> None:
    s = Settings(
        _env_file=None, backend_jwt_secret="x" * 32, llm_provider="groq",
        groq_api_key="gsk_real_secret", groq_model="m",
    )  # fmt: skip
    assert "gsk_real_secret" not in repr(s)


# --- Defensive JSON parsing -----------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        '{"headline": "Add FAQ"}',
        '```json\n{"headline": "Add FAQ"}\n```',
        'Sure! Here you go: {"headline": "Add FAQ"} Hope that helps.',
    ],
)
def test_parse_json_object_tolerates_wrapping(raw: str) -> None:
    assert llm.parse_json_object(raw) == {"headline": "Add FAQ"}


@pytest.mark.parametrize("raw", ["not json at all", "[1, 2, 3]", "{broken: json", ""])
def test_parse_json_object_rejects_garbage(raw: str) -> None:
    with pytest.raises(LLMError):
        llm.parse_json_object(raw)
