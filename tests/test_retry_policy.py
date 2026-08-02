"""Retry-Politik gegenueber den SPARQL-Endpoints (ARCH-014).

Retry-After, Jitter, Deckel und Gesamtbudget — geprueft am gemeinsamen
Retry-Kern, den SPARQL- und JSON-Requests teilen.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest
import respx

from fedlex_mcp import sparql_client as c

URL = "https://fedlex.data.admin.ch/sparqlendpoint"


def _resp(status: int, retry_after: str | None = None) -> httpx.Response:
    headers = {"Retry-After": retry_after} if retry_after is not None else {}
    return httpx.Response(status, headers=headers, request=httpx.Request("GET", URL))


async def _call(http, **kw):
    return await c._request_with_retry(
        http, "GET", URL, params=None, headers=None,
        base_delay=2.0, max_attempts=3, egress_check=None, on_retry=None, **kw
    )


class TestParseRetryAfter:
    def test_delta_seconds(self):
        assert c.parse_retry_after(_resp(429, "120")) == 120.0

    def test_http_date_in_the_future(self):
        when = datetime.now(UTC) + timedelta(seconds=90)
        got = c.parse_retry_after(_resp(503, format_datetime(when, usegmt=True)))
        assert got is not None
        assert 80 <= got <= 95

    def test_http_date_in_the_past_means_now(self):
        when = datetime.now(UTC) - timedelta(hours=1)
        assert c.parse_retry_after(_resp(503, format_datetime(when, usegmt=True))) == 0.0

    def test_absent_header(self):
        assert c.parse_retry_after(_resp(429)) is None

    def test_malformed_header_does_not_raise(self):
        assert c.parse_retry_after(_resp(429, "next Tuesday")) is None
        assert c.parse_retry_after(_resp(429, "")) is None
        assert c.parse_retry_after(_resp(429, "-5")) is None

    def test_ignored_on_other_statuses(self):
        assert c.parse_retry_after(_resp(500, "30")) is None

    def test_no_response_at_all(self):
        assert c.parse_retry_after(None) is None


class TestRetryDelay:
    def test_retry_after_beats_the_exponential_curve(self):
        # base_delay=2.0, attempt 0 spannt [1, 3] s — 9 kann nur aus dem Header kommen.
        exc = httpx.HTTPStatusError("429", request=None, response=_resp(429, "9"))
        assert 9.0 <= c.retry_delay(0, exc, 2.0) <= 9.0 * (1 + c.RETRY_AFTER_JITTER)

    def test_retry_after_is_never_undercut(self):
        exc = httpx.HTTPStatusError("429", request=None, response=_resp(429, "5"))
        for _ in range(50):
            assert c.retry_delay(0, exc, 2.0) >= 5.0

    def test_absurd_retry_after_is_capped(self):
        exc = httpx.HTTPStatusError("503", request=None, response=_resp(503, "86400"))
        delay = c.retry_delay(0, exc, 2.0)
        assert c.MAX_DELAY_S <= delay <= c.MAX_DELAY_S * (1 + c.RETRY_AFTER_JITTER)

    def test_exponential_ladder_is_capped(self):
        assert c.retry_delay(10, None, 2.0) <= c.MAX_DELAY_S * (1 + c.JITTER_SPREAD)

    def test_delay_is_spread(self):
        draws = {c.retry_delay(1, None, 2.0) for _ in range(30)}
        assert len(draws) > 1, "Wartezeit ist deterministisch — Jitter fehlt"
        base = 4.0
        assert all(
            base * (1 - c.JITTER_SPREAD) <= d <= base * (1 + c.JITTER_SPREAD) for d in draws
        )


@pytest.fixture
def fake_clock(monkeypatch):
    """Uhr, die nur vorrueckt, wenn der Client schlaeft.

    Ohne sie kann das Budget im Test nie ablaufen: Ausgepatchter Schlaf
    verbraucht keine Wanduhr, ``time.monotonic()`` bewegt sich nicht, und jede
    Deadline hielte ewig — der Test waere gruen, egal was die Logik tut.
    """
    now = {"t": 1000.0}
    slept: list[float] = []

    async def _sleep(seconds):
        slept.append(seconds)
        now["t"] += seconds

    monkeypatch.setattr(c.time, "monotonic", lambda: now["t"])
    monkeypatch.setattr(c.asyncio, "sleep", _sleep)
    return slept


@respx.mock
async def test_retry_after_reaches_the_sleep(fake_clock):
    respx.get(URL).mock(side_effect=[_resp(429, "7"), httpx.Response(200, json={})])
    async with httpx.AsyncClient() as http:
        await _call(http)
    assert len(fake_clock) == 1
    assert 7.0 <= fake_clock[0] <= 7.0 * (1 + c.RETRY_AFTER_JITTER)


@respx.mock
async def test_404_still_fails_fast_without_waiting(fake_clock):
    """4xx ausser 429 ist eine Aussage ueber die Anfrage, nicht ueber den Moment."""
    route = respx.get(URL).mock(return_value=httpx.Response(404))
    async with httpx.AsyncClient() as http:
        with pytest.raises(httpx.HTTPStatusError):
            await _call(http)
    assert route.call_count == 1
    assert fake_clock == []


@respx.mock
async def test_budget_cuts_the_ladder_short(fake_clock):
    route = respx.get(URL).mock(side_effect=httpx.ConnectError(""))
    async with httpx.AsyncClient() as http:
        with pytest.raises(httpx.ConnectError):
            await _call(http, total_budget=1.0)
    assert route.call_count < 3, "Budget hat die Leiter nicht begrenzt"
    assert route.call_count >= 1, "Der erste Versuch muss immer hinausgehen"


@respx.mock
async def test_full_ladder_runs_when_the_budget_allows(fake_clock):
    """Gegenrichtung: Ein weites Budget darf nichts abschneiden."""
    route = respx.get(URL).mock(side_effect=httpx.ConnectError(""))
    async with httpx.AsyncClient() as http:
        with pytest.raises(httpx.ConnectError):
            await _call(http, total_budget=600.0)
    assert route.call_count == 3


@respx.mock
async def test_per_request_timeout_is_clamped_to_the_remaining_budget(fake_clock):
    route = respx.get(URL).mock(return_value=httpx.Response(200, json={}))
    async with httpx.AsyncClient() as http:
        await _call(http, total_budget=4.0)
    sent = route.calls.last.request.extensions["timeout"]
    assert sent["read"] == pytest.approx(4.0), sent


def test_budget_deliberately_exceeds_the_mcp_client_default():
    """Beide Endpoints sind SPARQL — dokumentierte Ausnahme, als Entscheidung gepinnt.

    Geprueft wird die Abweichung, nicht die Konformitaet: So bleibt sie auf dem
    Papier, und eine spaetere stille Verengung scheitert laut.
    """
    from mcp.shared._httpx_utils import MCP_DEFAULT_TIMEOUT

    from fedlex_mcp.server import LINDAS_TIMEOUT, REQUEST_TIMEOUT

    assert c.TOTAL_BUDGET_S > MCP_DEFAULT_TIMEOUT
    assert c.TOTAL_BUDGET_S == REQUEST_TIMEOUT == LINDAS_TIMEOUT
