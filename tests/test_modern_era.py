"""Die Aera `2026-07-28` ueber den echten Draht — nicht nur ihre Konstanten.

`tests/test_protocol_version.py` pinnt die Revisionen und faehrt einen
Legacy-`initialize`. Was ein 2026-07-28-Client tatsaechlich zu sehen bekommt,
prueft dieses Modul: `server/discover` und `tools/call` als einzelne,
sitzungslose POSTs durch den zusammengebauten ASGI-Stack, dazu die
Logging-Frage in beiden Aeren.

Zwei Befunde aus v2.0.1 stehen hier als Zusicherung:

* `serverInfo.version` war ein Leerstring. Unter 2026-07-28 reist die Kennung
  als `_meta`-Stempel auf jeder Antwort, also auch der Leerstring.
* Jedes Tool rief `ctx.info()`/`ctx.error()`. Die Logging-Capability ist seit
  2026-07-28 abgekuendigt (SEP-2577); im Handshake ging die Notification ohne
  deklarierte `logging`-Capability raus, in der modernen Aera kam eine
  `MCPDeprecationWarning` pro Aufruf.
"""

from __future__ import annotations

import importlib.metadata
import json
import warnings

import httpx
import pytest
import respx
from mcp import Client
from mcp.shared.exceptions import MCPDeprecationWarning
from mcp.types.version import LATEST_MODERN_VERSION
from mcp_types import (
    CLIENT_CAPABILITIES_META_KEY,
    CLIENT_INFO_META_KEY,
    PROTOCOL_VERSION_META_KEY,
    SERVER_INFO_META_KEY,
)

from fedlex_mcp import server
from fedlex_mcp.server import build_http_app, mcp

PACKAGE_VERSION = importlib.metadata.version("fedlex-mcp")

_ENVELOPE = {
    PROTOCOL_VERSION_META_KEY: LATEST_MODERN_VERSION,
    CLIENT_INFO_META_KEY: {"name": "modern-client", "version": "1"},
    CLIENT_CAPABILITIES_META_KEY: {},
}

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


async def _modern_post(method: str, params: dict, name: str | None = None) -> httpx.Response:
    """Ein 2026-07-28-Request: kein `initialize`, keine Session, Envelope in `_meta`."""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Host": "127.0.0.1:8000",
        "Mcp-Protocol-Version": LATEST_MODERN_VERSION,
        "Mcp-Method": method,
    }
    if name is not None:
        headers["Mcp-Name"] = name
    app = build_http_app("127.0.0.1", 8000)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://127.0.0.1:8000"
        ) as client:
            return await client.post(
                "/mcp",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": method,
                    "params": {**params, "_meta": _ENVELOPE},
                },
            )


def _result(response: httpx.Response) -> dict:
    body = response.text
    for line in body.splitlines():  # SSE-Rahmen abstreifen, falls vorhanden
        if line.startswith("data: "):
            body = line[len("data: ") :]
    payload = json.loads(body)
    assert "error" not in payload, payload
    return payload["result"]


# ---------------------------------------------------------------------------
# server/discover — der Einstieg der modernen Aera
# ---------------------------------------------------------------------------


async def test_discover_nennt_die_moderne_revision() -> None:
    response = await _modern_post("server/discover", {})
    assert response.status_code == 200
    assert LATEST_MODERN_VERSION in _result(response)["supportedVersions"]


async def test_die_moderne_aera_oeffnet_keine_session() -> None:
    """Sessions gibt es auf Protokollebene nicht mehr. Ein `Mcp-Session-Id`
    auf einer 2026-07-28-Antwort hiesse, der Request sei im Legacy-Transport
    gelandet."""
    response = await _modern_post("server/discover", {})
    assert "mcp-session-id" not in response.headers


async def test_der_serverinfo_stempel_traegt_die_paketversion() -> None:
    info = _result(await _modern_post("server/discover", {}))["_meta"][SERVER_INFO_META_KEY]
    assert info["name"] == "fedlex_mcp"
    assert info["version"] == PACKAGE_VERSION, (
        f"serverInfo.version ist {info['version']!r}; ohne `version=` am "
        "MCPServer meldet das SDK einen Leerstring"
    )
    assert info["title"] == server.SERVER_TITLE
    assert info["websiteUrl"] == server.SERVER_WEBSITE


async def test_der_handshake_meldet_dieselbe_version() -> None:
    """Die Legacy-Aera liest dieselbe Identitaet — ein Feld, zwei Wege."""
    async with Client(mcp, mode="legacy") as client:
        assert client.server_info is not None
        assert client.server_info.version == PACKAGE_VERSION


# ---------------------------------------------------------------------------
# tools/call — ein Tool-Aufruf ohne Handshake
# ---------------------------------------------------------------------------


@respx.mock
async def test_ein_tool_antwortet_auf_einen_sitzungslosen_aufruf() -> None:
    respx.get(server.SPARQL_ENDPOINT).mock(return_value=httpx.Response(200, json=_BV))
    response = await _modern_post(
        "tools/call",
        {"name": "fedlex_get_law_by_sr", "arguments": {"params": {"sr_number": "101"}}},
        name="fedlex_get_law_by_sr",
    )
    assert response.status_code == 200
    assert "mcp-session-id" not in response.headers
    result = _result(response)
    assert result["isError"] is False
    assert result["structuredContent"]["match_type"] == "exact"
    assert result["_meta"][SERVER_INFO_META_KEY]["version"] == PACKAGE_VERSION


# ---------------------------------------------------------------------------
# Logging (SEP-2577) — in keiner Aera ein Seitenkanal
# ---------------------------------------------------------------------------


def _mock_fedlex(ok: bool) -> None:
    route = respx.get(server.SPARQL_ENDPOINT)
    if ok:
        route.mock(return_value=httpx.Response(200, json=_BV))
    else:
        route.mock(return_value=httpx.Response(500, text="kaputt"))


async def _call_and_collect(mode: str, ok: bool) -> tuple[list, list, dict]:
    received: list = []

    async def on_log(params) -> None:
        received.append(params)

    # Die moderne Aera verlangt ein Opt-in pro Request; ohne `log_level`
    # verwirft das SDK jede Nachricht, und der Test waere auch gegen den
    # alten Code gruen. Mit Opt-in muesste eine Nachricht ankommen, wenn der
    # Server noch eine schickte.
    kwargs = {"logging_callback": on_log}
    if mode != "legacy":
        kwargs["log_level"] = "debug"

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with respx.mock:
            _mock_fedlex(ok)
            async with Client(mcp, mode=mode, **kwargs) as client:
                capabilities = client.server_capabilities.model_dump(exclude_none=True)
                result = await client.call_tool(
                    "fedlex_get_law_by_sr", {"params": {"sr_number": "101"}}
                )
    assert result.structured_content["match_type"] == ("exact" if ok else "error")
    deprecations = [w for w in caught if issubclass(w.category, MCPDeprecationWarning)]
    return received, deprecations, capabilities


@pytest.mark.parametrize("ok", [True, False], ids=["erfolg", "fehler"])
@pytest.mark.parametrize("mode", ["legacy", "auto"])
async def test_kein_tool_sendet_log_notifications(mode: str, ok: bool) -> None:
    received, _, capabilities = await _call_and_collect(mode, ok)
    assert "logging" not in capabilities
    assert received == [], (
        f"der Server schickte {len(received)} notifications/message, ohne die "
        "logging-Capability zu deklarieren"
    )


@pytest.mark.parametrize("ok", [True, False], ids=["erfolg", "fehler"])
@pytest.mark.parametrize("mode", ["legacy", "auto"])
async def test_kein_tool_ruft_eine_abgekuendigte_sdk_funktion(mode: str, ok: bool) -> None:
    _, deprecations, _ = await _call_and_collect(mode, ok)
    assert deprecations == [], [str(w.message) for w in deprecations]
