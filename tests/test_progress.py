"""SDK-003: `notifications/progress` für lange SPARQL-Aufrufe.

Gemeldet wird jeder Versuch gegen einen Endpunkt, bei einem Retry mit dem
Grund des vorigen Fehlschlags; `total` bleibt leer. Geprüft über einen echten
`Client` in beiden Ären, dazu über Streamable HTTP in 2026-07-28 — dort
wechselt die Antwort für Fortschritt auf SSE, und das ist der Weg, auf dem ein
Browser- oder Remote-Client die Meldungen überhaupt sieht.
"""

from __future__ import annotations

import json
import warnings

import httpx
import pytest
import respx
from mcp import Client
from mcp.server.mcpserver import Context
from mcp.types.version import LATEST_MODERN_VERSION
from mcp_types import (
    CLIENT_CAPABILITIES_META_KEY,
    CLIENT_INFO_META_KEY,
    PROTOCOL_VERSION_META_KEY,
)

from fedlex_mcp import server, sparql_client
from fedlex_mcp.server import GetLawBySrInput, build_http_app, mcp

MODES = ["legacy", "auto"]

_BV = {
    "results": {
        "bindings": [
            {
                "ca": {"value": "https://fedlex.data.admin.ch/eli/cc/1999/404"},
                "title": {"value": "Bundesverfassung der Schweizerischen Eidgenossenschaft"},
                "titleShort": {"value": "BV"},
                "srNumber": {"value": "101"},
                "inForceStatus": {
                    "value": "https://fedlex.data.admin.ch/vocabulary/enforcement-status/0"
                },
            }
        ]
    }
}
_EMPTY = {"results": {"bindings": []}}


@pytest.fixture(autouse=True)
def _kein_warten(monkeypatch):
    """Retries ohne echte Wartezeit — über den Modul-Alias, nicht `asyncio.sleep`
    (CLAUDE.md, Teil 1, Tests)."""

    async def _nicht(_seconds: float) -> None:
        return None

    monkeypatch.setattr(sparql_client, "_sleep", _nicht)


async def _call(mode: str, tool: str, params: dict) -> tuple[list, object]:
    received: list = []

    async def on_progress(progress, total, message) -> None:
        received.append((progress, total, message))

    async with Client(mcp, mode=mode) as client:
        result = await client.call_tool(tool, {"params": params}, progress_callback=on_progress)
    return received, result


@pytest.mark.parametrize("mode", MODES)
async def test_ein_aufruf_meldet_seinen_versuch(mode: str) -> None:
    with respx.mock:
        respx.get(server.SPARQL_ENDPOINT).mock(return_value=httpx.Response(200, json=_BV))
        received, result = await _call(mode, "fedlex_get_law_by_sr", {"sr_number": "101"})
    assert result.is_error is False
    assert received, "kein notifications/progress angekommen"
    progress, total, message = received[0]
    assert progress == 1
    assert total is None, "ein Total wäre erfunden"
    assert message == f"Anfrage an Fedlex (Versuch 1 von {server.RETRY_MAX_ATTEMPTS})"


@pytest.mark.parametrize("mode", MODES)
async def test_ein_retry_meldet_versuch_und_grund(mode: str) -> None:
    """Der Fall, für den es die Meldungen gibt: Die Zeit steckt im Retry."""
    with respx.mock:
        respx.get(server.SPARQL_ENDPOINT).mock(
            side_effect=[httpx.Response(503), httpx.Response(200, json=_BV)]
        )
        received, result = await _call(mode, "fedlex_get_law_by_sr", {"sr_number": "101"})
    assert result.is_error is False
    messages = [m for _, _, m in received]
    assert messages[:2] == [
        f"Anfrage an Fedlex (Versuch 1 von {server.RETRY_MAX_ATTEMPTS})",
        f"Fedlex: Versuch 2 von {server.RETRY_MAX_ATTEMPTS} nach HTTP 503",
    ]


@pytest.mark.parametrize("mode", MODES)
async def test_der_fortschritt_steigt_streng_monoton(mode: str) -> None:
    """Die Spec verlangt steigende Werte. Zwei Retries plus Erfolg: drei
    Schritte, in dieser Reihenfolge — auch die per Task verschickten."""
    with respx.mock:
        respx.get(server.SPARQL_ENDPOINT).mock(
            side_effect=[
                httpx.Response(503),
                httpx.ConnectError("weg"),
                httpx.Response(200, json=_BV),
            ]
        )
        received, _ = await _call(mode, "fedlex_get_law_by_sr", {"sr_number": "101"})
    values = [p for p, _, _ in received]
    assert values[:3] == [1, 2, 3]
    assert values == sorted(set(values)), values
    assert received[2][2].endswith("nach Verbindungsfehler")


@pytest.mark.parametrize("mode", MODES)
async def test_lindas_nennt_termdat(mode: str) -> None:
    with respx.mock:
        respx.get(server.LINDAS_ENDPOINT).mock(return_value=httpx.Response(200, json=_EMPTY))
        received, _ = await _call(mode, "termdat_lookup_term", {"term": "Schule"})
    assert received[0][2].startswith("Anfrage an TERMDAT (LINDAS)")


@pytest.mark.parametrize("mode", MODES)
async def test_ohne_token_keine_meldung_und_keine_warnung(mode: str) -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with respx.mock:
            respx.get(server.SPARQL_ENDPOINT).mock(return_value=httpx.Response(200, json=_BV))
            async with Client(mcp, mode=mode) as client:
                result = await client.call_tool(
                    "fedlex_get_law_by_sr", {"params": {"sr_number": "101"}}
                )
    assert result.is_error is False
    assert [str(w.message) for w in caught] == []


async def test_ein_kaputter_fortschritt_kippt_den_aufruf_nicht(monkeypatch) -> None:
    """Fortschritt ist Beiwerk. Scheitert die Meldung, gilt das Resultat."""

    async def kaputt(self, *args, **kwargs) -> None:
        raise RuntimeError("Stream zu")

    monkeypatch.setattr(Context, "report_progress", kaputt)
    with respx.mock:
        respx.get(server.SPARQL_ENDPOINT).mock(
            side_effect=[httpx.Response(503), httpx.Response(200, json=_BV)]
        )
        _, result = await _call("auto", "fedlex_get_law_by_sr", {"sr_number": "101"})
    assert result.is_error is False
    assert result.structured_content["match_type"] == "exact"


@respx.mock
async def test_der_direktaufruf_meldet_nichts_und_laeuft() -> None:
    respx.get(server.SPARQL_ENDPOINT).mock(return_value=httpx.Response(200, json=_BV))
    resp = await server.fedlex_get_law_by_sr(GetLawBySrInput(sr_number="101"))
    assert resp.match_type == "exact"
    assert server._progress.get() is None


@respx.mock
async def test_streamable_http_liefert_den_fortschritt_vor_dem_resultat() -> None:
    """2026-07-28 über den Draht: ein sitzungsloser POST mit `progressToken`
    bekommt SSE, zuerst `notifications/progress`, dann das Resultat."""
    respx.get(server.SPARQL_ENDPOINT).mock(return_value=httpx.Response(200, json=_BV))
    meta = {
        PROTOCOL_VERSION_META_KEY: LATEST_MODERN_VERSION,
        CLIENT_INFO_META_KEY: {"name": "modern-client", "version": "1"},
        CLIENT_CAPABILITIES_META_KEY: {},
        "progressToken": "fortschritt-1",
    }
    app = build_http_app("127.0.0.1", 8000)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8000"
        ) as client:
            response = await client.post(
                "/mcp",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "Host": "127.0.0.1:8000",
                    "Mcp-Protocol-Version": LATEST_MODERN_VERSION,
                    "Mcp-Method": "tools/call",
                    "Mcp-Name": "fedlex_get_law_by_sr",
                },
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "fedlex_get_law_by_sr",
                        "arguments": {"params": {"sr_number": "101"}},
                        "_meta": meta,
                    },
                },
            )
    assert response.headers["content-type"].startswith("text/event-stream")
    frames = [
        json.loads(line[len("data: ") :])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert frames[0]["method"] == "notifications/progress"
    assert frames[0]["params"]["progressToken"] == "fortschritt-1"
    assert frames[0]["params"]["progress"] == 1
    assert frames[-1]["result"]["isError"] is False


async def test_drain_wartet_die_meldungen_aus_dem_retry_callback_ab() -> None:
    """`note()` verschickt per Task; `drain()` wartet sie vor dem Resultat ab.

    Über den Draht ist das nur teilweise zu sehen: Gegengeprobt am 2026-09-27
    fallen ohne `drain()` die Retry-Fälle der Legacy-Ära (die Meldung kommt
    NACH dem Resultat), die der modernen bleiben grün. Darum zusätzlich direkt
    an `_Progress`, unabhängig vom Transport."""

    class _Ctx:
        def __init__(self) -> None:
            self.sent: list[tuple] = []

        async def report_progress(self, progress, total=None, message=None) -> None:
            self.sent.append((progress, total, message))

    ctx = _Ctx()
    progress = server._Progress(ctx)  # type: ignore[arg-type]
    progress.note("eins")
    progress.note("zwei")
    assert ctx.sent == []  # noch nicht verschickt: Tasks, kein await
    await progress.drain()
    assert ctx.sent == [(1, None, "eins"), (2, None, "zwei")]
