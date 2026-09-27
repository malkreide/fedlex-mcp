"""OBS-001: ein Ausführungsfehler ist ein Tool-Resultat mit `isError: true`.

Ein Ausführungsfehler ist nach Spec ein Tool-Resultat mit `isError: true`,
keine JSON-RPC-Fehlerantwort. Bis v2.0.1 kam ein
Ausfall von Fedlex oder LINDAS als gewöhnliches Resultat mit `isError: false`
zurück; nur `match_type: "error"` im Envelope sagte, dass nichts gefunden,
sondern nichts gefragt worden war.

Geprüft über einen echten `Client` in beiden Ären und für JEDES registrierte
Tool — die Namen kommen aus `tools/list`, nicht aus einer Liste hier. Ein
Tool, das jemand künftig mit `@mcp.tool` statt `@_tool` registriert, fällt
damit auf, statt still ohne Flag durchzulaufen.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx
from mcp import Client

from fedlex_mcp import server, sparql_client
from fedlex_mcp.server import GetLawBySrInput, mcp

# Minimal gültige Argumente je Tool. Die Schlüssel werden gegen `tools/list`
# geprüft: ein neues Tool ohne Eintrag hier macht den Test rot, nicht leer.
ARGUMENTS: dict[str, dict] = {
    "fedlex_search_laws": {"keywords": "Datenschutz"},
    "fedlex_get_law_by_sr": {"sr_number": "101"},
    "fedlex_get_recent_publications": {},
    "fedlex_get_upcoming_changes": {},
    "fedlex_search_gazette": {"keywords": "Berufsbildung"},
    "fedlex_get_law_history": {"sr_number": "235.1"},
    "fedlex_search_treaties": {},
    "fedlex_get_open_consultations": {},
    "fedlex_search_consultations": {},
    "fedlex_get_consultation": {"event_id": "proj/2024/1/cons_1"},
    "termdat_lookup_term": {"term": "Schule"},
    "termdat_get_concept": {"concept": "40109"},
}

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


@pytest.fixture(autouse=True)
def _kein_warten(monkeypatch):
    """Ein Ausfall läuft durch die Retry-Policy; ohne diesen Patch schläft jeder
    Fall echte Sekunden. Gepatcht wird der Modul-Alias, nicht `asyncio.sleep`
    (siehe CLAUDE.md, Teil 1, Tests)."""

    async def _nicht(_seconds: float) -> None:
        return None

    monkeypatch.setattr(sparql_client, "_sleep", _nicht)


def _down() -> None:
    """Beide Endpunkte unerreichbar — der Ausführungsfehler schlechthin."""
    for endpoint in (server.SPARQL_ENDPOINT, server.LINDAS_ENDPOINT):
        respx.route(url__startswith=endpoint).mock(side_effect=httpx.ConnectError("weg"))


async def test_jedes_registrierte_tool_hat_testargumente() -> None:
    async with Client(mcp) as client:
        names = {tool.name for tool in (await client.list_tools()).tools}
    assert names == set(ARGUMENTS)


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("tool", sorted(ARGUMENTS))
async def test_ein_ausfall_ist_ein_tool_fehler(tool: str, mode: str) -> None:
    with respx.mock:
        _down()
        async with Client(mcp, mode=mode) as client:
            result = await client.call_tool(tool, {"params": ARGUMENTS[tool]})
    assert result.is_error is True, f"{tool} meldete einen Ausfall mit isError=false"
    assert result.structured_content["match_type"] == "error"
    assert result.structured_content["tool"] == tool


@pytest.mark.parametrize("mode", MODES)
async def test_der_fehler_behaelt_envelope_und_textform(mode: str) -> None:
    """`structuredContent` bleibt, und der Text ist derselbe Envelope — ein
    Client ohne `structuredContent` sieht dieselbe Form wie im Erfolgsfall."""
    with respx.mock:
        _down()
        async with Client(mcp, mode=mode) as client:
            result = await client.call_tool(
                "fedlex_get_law_by_sr", {"params": {"sr_number": "101"}}
            )
    envelope = result.structured_content
    assert envelope["message"], "die maskierte Meldung fehlt"
    assert envelope["count"] == 0 and envelope["results"] == []
    assert len(result.content) == 1
    assert json.loads(result.content[0].text) == envelope


@pytest.mark.parametrize("mode", MODES)
async def test_ein_treffer_ist_kein_fehler(mode: str) -> None:
    with respx.mock:
        respx.get(server.SPARQL_ENDPOINT).mock(return_value=httpx.Response(200, json=_BV))
        async with Client(mcp, mode=mode) as client:
            result = await client.call_tool(
                "fedlex_get_law_by_sr", {"params": {"sr_number": "101"}}
            )
    assert result.is_error is False
    assert result.structured_content["match_type"] == "exact"


@pytest.mark.parametrize("mode", MODES)
async def test_kein_treffer_ist_kein_fehler(mode: str) -> None:
    """Die Unterscheidung, um die es geht: «nichts gefunden» ist eine gültige
    Antwort der Quelle. Trüge sie das Flag, läse das Modell eine leere Suche
    als Störung und versuchte es erneut."""
    empty = {"results": {"bindings": []}}
    with respx.mock:
        respx.get(server.SPARQL_ENDPOINT).mock(return_value=httpx.Response(200, json=empty))
        async with Client(mcp, mode=mode) as client:
            result = await client.call_tool(
                "fedlex_search_laws", {"params": {"keywords": "Gibtesnicht"}}
            )
    assert result.is_error is False
    assert result.structured_content["match_type"] == "none"


@pytest.mark.parametrize("mode", MODES)
async def test_einen_schemafehler_beantwortet_das_sdk(mode: str) -> None:
    """Ungültige Argumente erreichen das Tool gar nicht. Seit 2025-11-25 sind
    sie trotzdem ein Ausführungsfehler (`isError: true`, damit das Modell die
    Eingabe korrigieren kann) — aber einer des SDK, ohne Envelope. Fällt
    `structuredContent is None`, liefe die Validierung erst im Tool."""
    async with Client(mcp, mode=mode) as client:
        result = await client.call_tool("fedlex_get_law_by_sr", {"params": {"sr_number": "x"}})
    assert result.is_error is True
    assert result.structured_content is None


@respx.mock
async def test_der_direktaufruf_liefert_weiter_den_envelope() -> None:
    """Das Flag setzt nur der beim SDK registrierte Wrapper; die Funktion im
    Modul bleibt, was sie war — darauf bauen die Unit-Tests in test_server.py."""
    _down()
    resp = await server.fedlex_get_law_by_sr(GetLawBySrInput(sr_number="101"))
    assert isinstance(resp, server.FedlexResponse)
    assert resp.match_type == "error"
