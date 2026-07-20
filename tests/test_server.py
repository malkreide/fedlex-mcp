"""Unit tests for fedlex-mcp server.

Network is mocked with respx so the suite is fully offline (CI: pytest -m
'not live'). A single live smoke test against the real SPARQL endpoint is
marked `live` and skipped by default.

Tools return a structured ``FedlexResponse`` envelope (SDK-002): assertions
check ``.results`` / ``.match_type`` / ``.count`` for structure and ``.markdown``
for the human-readable rendering.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx
from pydantic import ValidationError

from fedlex_mcp import consultations, server
from fedlex_mcp.server import (
    GetConsultationInput,
    GetLawBySrInput,
    GetLawHistoryInput,
    GetOpenConsultationsInput,
    GetRecentPublicationsInput,
    GetUpcomingChangesInput,
    Language,
    SearchConsultationsInput,
    SearchGazetteInput,
    SearchLawsInput,
    SearchTreatiesInput,
    TermdatGetConceptInput,
    TermdatLookupInput,
    sparql_escape,
)

ENDPOINT = server.SPARQL_ENDPOINT
LINDAS = server.LINDAS_ENDPOINT


def _sparql_response(bindings: list[dict]) -> httpx.Response:
    return httpx.Response(200, json={"results": {"bindings": bindings}})


def _binding(**fields: str) -> dict:
    return {k: {"value": v} for k, v in fields.items()}


# ---------------------------------------------------------------------------
# Pure-function unit tests
# ---------------------------------------------------------------------------

def test_sparql_escape_neutralises_quote_breakout() -> None:
    assert sparql_escape('foo" } INJECT') == 'foo\\" } INJECT'


def test_sparql_escape_handles_backslash_and_newline() -> None:
    assert sparql_escape("a\\b\nc") == "a\\\\b\\nc"


def test_status_label_known_and_unknown() -> None:
    assert "In Kraft" in server.status_label(server.STATUS_IN_FORCE)
    assert server.status_label("https://x/vocabulary/enforcement-status/9") == "(9)"


def test_fedlex_url_rewrites_data_uri() -> None:
    url = server.fedlex_url("https://fedlex.data.admin.ch/eli/cc/235.1", "fr")
    assert url == "https://www.fedlex.admin.ch/eli/cc/235.1/fr"


def test_assert_host_allowed_blocks_foreign_host() -> None:
    server.assert_host_allowed(ENDPOINT)  # allow-listed -> no raise
    with pytest.raises(PermissionError):
        server.assert_host_allowed("https://evil.example.com/x")


# ---------------------------------------------------------------------------
# Input validation (SEC-018)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad", ['a" } INJECT', "back\\slash", "brace{", "<tag>"])
def test_keywords_pattern_rejects_injection(bad: str) -> None:
    with pytest.raises(ValidationError):
        SearchLawsInput(keywords=bad)


@pytest.mark.parametrize("good", ["Datenschutz", "CO2-Gesetz", "Müller", "EU/EFTA"])
def test_keywords_pattern_accepts_legitimate_terms(good: str) -> None:
    assert SearchLawsInput(keywords=good).keywords == good


@pytest.mark.parametrize("bad", ["1; DROP", '235" .', "abc", "235,1"])
def test_sr_number_pattern_rejects_malformed(bad: str) -> None:
    with pytest.raises(ValidationError):
        GetLawBySrInput(sr_number=bad)


@pytest.mark.parametrize("good", ["101", "235.1", "412.10", "0.101"])
def test_sr_number_pattern_accepts_valid(good: str) -> None:
    assert GetLawBySrInput(sr_number=good).sr_number == good


def test_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        SearchLawsInput(keywords="Datenschutz", unexpected="x")


def test_limit_out_of_range_rejected() -> None:
    with pytest.raises(ValidationError):
        SearchLawsInput(keywords="Datenschutz", limit=999)


# ---------------------------------------------------------------------------
# Tool happy-paths — structured envelope (SDK-002)
# ---------------------------------------------------------------------------

@respx.mock
@pytest.mark.asyncio
async def test_search_laws_happy() -> None:
    respx.get(ENDPOINT).mock(return_value=_sparql_response([
        _binding(ca="https://fedlex.data.admin.ch/eli/cc/235.1",
                 title="Bundesgesetz über den Datenschutz", titleShort="DSG",
                 srNumber="235.1", inForceStatus=server.STATUS_IN_FORCE),
    ]))
    resp = await server.fedlex_search_laws(SearchLawsInput(keywords="Datenschutz"))
    assert resp.match_type == "exact"
    assert resp.count == 1
    assert resp.results[0]["sr_number"] == "235.1"
    assert resp.results[0]["title_short"] == "DSG"
    assert resp.results[0]["url"].startswith("https://www.fedlex.admin.ch/")
    assert resp.source.startswith("Fedlex")
    assert "DSG" in resp.markdown


@respx.mock
@pytest.mark.asyncio
async def test_search_laws_empty_envelope() -> None:
    respx.get(ENDPOINT).mock(return_value=_sparql_response([]))
    resp = await server.fedlex_search_laws(SearchLawsInput(keywords="zzzznope"))
    assert resp.match_type == "none"
    assert resp.count == 0
    assert resp.results == []
    assert "match_type: none" in resp.markdown


@respx.mock
@pytest.mark.asyncio
async def test_get_law_by_sr_happy() -> None:
    respx.get(ENDPOINT).mock(return_value=_sparql_response([
        _binding(ca="https://fedlex.data.admin.ch/eli/cc/101",
                 title="Bundesverfassung", titleShort="BV", srNumber="101",
                 inForceStatus=server.STATUS_IN_FORCE, entryDate="2000-01-01"),
    ]))
    resp = await server.fedlex_get_law_by_sr(GetLawBySrInput(sr_number="101"))
    assert resp.count == 1
    assert resp.results[0]["title"] == "Bundesverfassung"
    assert "Bundesverfassung" in resp.markdown


@respx.mock
@pytest.mark.asyncio
async def test_get_recent_publications_happy() -> None:
    respx.get(ENDPOINT).mock(return_value=_sparql_response([
        _binding(act="https://fedlex.data.admin.ch/eli/oc/2026/1",
                 title="Neue Verordnung", pubDate="2026-05-01"),
    ]))
    resp = await server.fedlex_get_recent_publications(GetRecentPublicationsInput(days=30))
    assert resp.results[0]["publication_date"] == "2026-05-01"
    assert "Neue Verordnung" in resp.markdown


@respx.mock
@pytest.mark.asyncio
async def test_get_upcoming_changes_happy() -> None:
    respx.get(ENDPOINT).mock(return_value=_sparql_response([
        _binding(ca="https://fedlex.data.admin.ch/eli/cc/999",
                 title="Künftiges Gesetz", titleShort="KG", srNumber="999",
                 entryDate="2026-12-01"),
    ]))
    resp = await server.fedlex_get_upcoming_changes(GetUpcomingChangesInput(days_ahead=90))
    assert resp.results[0]["entry_date"] == "2026-12-01"
    assert "Künftiges Gesetz" in resp.markdown


@respx.mock
@pytest.mark.asyncio
async def test_search_gazette_happy() -> None:
    respx.get(ENDPOINT).mock(return_value=_sparql_response([
        _binding(act="https://fedlex.data.admin.ch/eli/fga/2024/1",
                 title="Botschaft zur Berufsbildung", pubDate="2024-03-01"),
    ]))
    resp = await server.fedlex_search_gazette(SearchGazetteInput(keywords="Berufsbildung", year=2024))
    assert resp.count == 1
    assert "Berufsbildung" in resp.markdown


@respx.mock
@pytest.mark.asyncio
async def test_get_law_history_happy() -> None:
    respx.get(ENDPOINT).mock(return_value=_sparql_response([
        _binding(ca="https://fedlex.data.admin.ch/eli/cc/235.1/2023",
                 title="DSG", srNumber="235.1", entryDate="2023-09-01",
                 inForceStatus=server.STATUS_IN_FORCE),
        _binding(ca="https://fedlex.data.admin.ch/eli/cc/235.1/1993",
                 title="DSG", srNumber="235.1", entryDate="1993-07-01",
                 inForceStatus=server.STATUS_NO_LONGER_FORCE),
    ]))
    resp = await server.fedlex_get_law_history(GetLawHistoryInput(sr_number="235.1"))
    assert resp.count == 2
    assert {r["version"] for r in resp.results} == {1, 2}
    assert "Versionsgeschichte" in resp.markdown


@respx.mock
@pytest.mark.asyncio
async def test_search_treaties_happy() -> None:
    respx.get(ENDPOINT).mock(return_value=_sparql_response([
        _binding(ca="https://fedlex.data.admin.ch/eli/cc/0.101",
                 title="EMRK", srNumber="0.101", entryDate="1974-11-28"),
    ]))
    resp = await server.fedlex_search_treaties(SearchTreatiesInput(keywords="EMRK"))
    assert resp.results[0]["sr_number"] == "0.101"


# ---------------------------------------------------------------------------
# Error handling (OBS-001 / OBS-002) — masked, structured error envelope
# ---------------------------------------------------------------------------

@respx.mock
@pytest.mark.asyncio
async def test_http_400_returns_error_envelope() -> None:
    respx.get(ENDPOINT).mock(return_value=httpx.Response(400, text="boom"))
    resp = await server.fedlex_search_laws(SearchLawsInput(keywords="Datenschutz"))
    assert resp.match_type == "error"
    assert "HTTP 400" in resp.markdown
    assert "boom" not in resp.markdown


@respx.mock
@pytest.mark.asyncio
async def test_connect_error_is_masked() -> None:
    respx.get(ENDPOINT).mock(side_effect=httpx.ConnectError("dns fail"))
    resp = await server.fedlex_search_laws(SearchLawsInput(keywords="Datenschutz"))
    assert resp.match_type == "error"
    assert "Verbindung zu Fedlex" in resp.markdown
    assert "dns fail" not in resp.markdown


def test_handle_error_generic_does_not_leak_repr() -> None:
    out = server.handle_error("fedlex_search_laws", ValueError("secret-internal-detail"))
    assert "secret-internal-detail" not in out
    assert out.startswith("Fehler:")


# ---------------------------------------------------------------------------
# Config / wiring / observability
# ---------------------------------------------------------------------------

def test_shared_client_default_is_none_outside_lifespan() -> None:
    assert server._http_client is None


def test_settings_defaults_are_safe() -> None:
    assert server.settings.transport == "stdio"
    assert server.settings.host == "127.0.0.1"  # no 0.0.0.0 default (SEC-016)


def test_egress_allow_list_is_frozen() -> None:
    assert isinstance(server.ALLOWED_EGRESS_HOSTS, frozenset)
    assert server.FEDLEX_DATA_HOST in server.ALLOWED_EGRESS_HOSTS


def test_structured_logger_available() -> None:
    assert server.log is not None
    assert hasattr(server.log, "info")


def test_tracing_disabled_by_default() -> None:
    """OBS-006: OpenTelemetry is a no-op unless explicitly configured."""
    assert server._tracer is None


def test_server_imports() -> None:
    assert hasattr(server, "mcp")


@respx.mock
@pytest.mark.asyncio
async def test_tool_accepts_ctx_none() -> None:
    respx.get(ENDPOINT).mock(return_value=_sparql_response([
        _binding(ca="https://fedlex.data.admin.ch/eli/cc/101", title="BV", srNumber="101"),
    ]))
    resp = await server.fedlex_search_laws(SearchLawsInput(keywords="Verfassung"), ctx=None)
    assert resp.count == 1


@pytest.mark.parametrize("sr_number", ["101", "210.10", "172.021"])
def test_sr_number_format_valid(sr_number: str) -> None:
    assert re.match(server.SR_NUMBER_PATTERN, sr_number)


# ---------------------------------------------------------------------------
# Tool-definition hash pinning (SEC-022)
# ---------------------------------------------------------------------------

def test_tool_definitions_match_lock() -> None:
    """The live tool definitions must match the committed lock file. If this
    fails, a tool changed — regenerate with scripts/snapshot_tools.py and note
    it in CHANGELOG.md (rug-pull guard)."""
    lock_path = Path(__file__).resolve().parent.parent / "tool-definitions.lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    live = asyncio.run(server.compute_tool_signature_hash())
    assert live == lock["sha256"], (
        "Tool definitions drifted from tool-definitions.lock.json. "
        "Run: PYTHONPATH=src python scripts/snapshot_tools.py"
    )


# ---------------------------------------------------------------------------
# Tool allow-list (SEC-014) — default-deny via FEDLEX_ENABLED_TOOLS
# ---------------------------------------------------------------------------

def test_tool_allowlist_default_exposes_all() -> None:
    names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert len(names) == 12


def test_tool_allowlist_env_default_deny() -> None:
    """With FEDLEX_ENABLED_TOOLS set, only listed tools are registered.

    Runs in a subprocess so the module-load-time allow-list does not leak into
    the rest of the suite.
    """
    code = (
        "import asyncio;from fedlex_mcp import server as s;"
        "print(sorted(t.name for t in asyncio.run(s.mcp.list_tools())))"
    )
    env = {
        **os.environ,
        "FEDLEX_ENABLED_TOOLS": "fedlex_search_laws,fedlex_get_law_by_sr",
        "PYTHONPATH": "src",
    }
    out = subprocess.check_output([sys.executable, "-c", code], env=env, text=True)
    assert "fedlex_search_laws" in out
    assert "fedlex_get_law_by_sr" in out
    assert "fedlex_search_treaties" not in out


# ===========================================================================
# v1.1.0 — Vernehmlassungen (Fedlex) & TERMDAT (LINDAS)
# ===========================================================================

CONS_URI = "https://fedlex.data.admin.ch/eli/dl/proj/2026/71/cons_1"


def _open_cons_binding(end: str, status: str = server.CONSULTATION_STATUS_RUNNING,
                       title: str = "Bildungsreform Volksschule") -> dict:
    return _binding(
        c=CONS_URI, eventId="proj/2026/71/cons_1", title=title, status=status,
        start="2026-06-01", end=end, instLabel="Departement für Bildung",
        inst2Label="Bundesamt für Kultur",
    )


# --- Happy paths (new tools) ------------------------------------------------

@respx.mock
@pytest.mark.asyncio
async def test_open_consultations_happy() -> None:
    respx.get(ENDPOINT).mock(return_value=_sparql_response([_open_cons_binding("2099-09-01")]))
    resp = await server.fedlex_get_open_consultations(GetOpenConsultationsInput(keyword="Bildung"))
    assert resp.match_type == "exact"
    assert resp.count == 1
    r = resp.results[0]
    assert r["event_id"] == "proj/2026/71/cons_1"
    assert r["deadline"] == "2099-09-01"
    assert r["lead_department"] == "Departement für Bildung"
    assert r["status_conflict"] is False
    assert resp.source == server.ATTRIBUTION_FEDLEX
    assert "Volksschule" in resp.markdown


@respx.mock
@pytest.mark.asyncio
async def test_open_consultations_empty_states_timestamp() -> None:
    respx.get(ENDPOINT).mock(return_value=_sparql_response([]))
    resp = await server.fedlex_get_open_consultations(GetOpenConsultationsInput())
    assert resp.match_type == "none"
    assert resp.count == 0
    assert "keine offenen Vernehmlassungen" in resp.message
    assert "geprüft" in resp.message
    assert "Europe/Zurich" in resp.message


@respx.mock
@pytest.mark.asyncio
async def test_search_consultations_happy() -> None:
    respx.get(ENDPOINT).mock(return_value=_sparql_response([
        _open_cons_binding("2026-03-01", status=server.CONSULTATION_STATUS_BASE + "5"),
    ]))
    resp = await server.fedlex_search_consultations(
        SearchConsultationsInput(keyword="Bildung", status="closed")
    )
    assert resp.count == 1
    assert resp.results[0]["status"] == "Abgeschlossen"


@respx.mock
@pytest.mark.asyncio
async def test_get_consultation_happy() -> None:
    respx.get(ENDPOINT).mock(return_value=_sparql_response([
        _binding(c=CONS_URI, title="Bildungsreform", desc="Beschreibung der Vorlage",
                 status=server.CONSULTATION_STATUS_RUNNING, start="2026-06-01", end="2099-09-01",
                 instLabel="Departement für Bildung", inst2Label="Bundesamt für Kultur",
                 draft="https://fedlex.data.admin.ch/eli/dl/proj/2026/71/cons_1/doc_1",
                 impact="https://fedlex.data.admin.ch/eli/cc/2014/771"),
    ]))
    resp = await server.fedlex_get_consultation(GetConsultationInput(event_id="proj/2026/71/cons_1"))
    assert resp.count == 1
    r = resp.results[0]
    assert r["deadline"] == "2099-09-01"
    assert len(r["draft_documents"]) == 1
    assert len(r["related_legal_resource"]) == 1
    assert "Vernehmlassungsunterlagen" in resp.markdown


@respx.mock
@pytest.mark.asyncio
async def test_termdat_lookup_happy() -> None:
    respx.get(LINDAS).mock(side_effect=[
        _sparql_response([_binding(s="https://register.ld.admin.ch/termdat/40109/3/de",
                                   name="Volksschule")]),
        _sparql_response([
            _binding(c="https://register.ld.admin.ch/termdat/40109", id="40109",
                     name="obligatorische Schule", nl="de", desc="Bildungsstufe …", dl="de"),
            _binding(c="https://register.ld.admin.ch/termdat/40109", id="40109",
                     name="scolarité obligatoire", nl="fr"),
            _binding(c="https://register.ld.admin.ch/termdat/40109", id="40109",
                     name="scuola dell'obbligo", nl="it"),
        ]),
    ])
    resp = await server.termdat_lookup_term(
        TermdatLookupInput(term="Volksschule", target_languages=["de", "fr", "it"])
    )
    assert resp.count == 1
    r = resp.results[0]
    assert r["concept_id"] == "40109"
    assert r["names"]["fr"] == "scolarité obligatoire"
    assert r["names"]["it"] == "scuola dell'obbligo"
    # Teilbestand-Attribution muss in JEDER TERMDAT-Response stehen.
    assert "77,692" in resp.source
    assert "Partial dataset" in resp.markdown


@respx.mock
@pytest.mark.asyncio
async def test_termdat_lookup_negative_flags_partial_dataset() -> None:
    respx.get(LINDAS).mock(return_value=_sparql_response([]))
    resp = await server.termdat_lookup_term(TermdatLookupInput(term="Nichtvorhandenerbegriff"))
    assert resp.match_type == "none"
    assert "nicht als Linked Data publiziert" in resp.message
    assert "Partial dataset" in resp.markdown


@respx.mock
@pytest.mark.asyncio
async def test_termdat_get_concept_happy_accepts_term_uri() -> None:
    respx.get(LINDAS).mock(side_effect=[
        _sparql_response([
            _binding(name="obligatorische Schule", nl="de", desc="Bildungsstufe …", dl="de",
                     url="https://www.termdat.bk.admin.ch/entry/40109",
                     mod="2021-05-12T09:32:03Z"),
            _binding(name="compulsory education", nl="en"),
        ]),
        _sparql_response([
            _binding(syn="https://register.ld.admin.ch/termdat/40109/3/de", name="Volksschule", nl="de"),
        ]),
    ])
    # Term-URI mit Suffix muss auf Konzept 40109 normalisiert werden (Quirk 3).
    resp = await server.termdat_get_concept(
        TermdatGetConceptInput(concept="https://register.ld.admin.ch/termdat/40109/3/de")
    )
    assert resp.count == 1
    assert resp.results[0]["concept_id"] == "40109"
    assert resp.results[0]["names"]["en"] == "compulsory education"
    assert resp.results[0]["synonyms"][0]["name"] == "Volksschule"


def test_termdat_get_concept_invalid_reference() -> None:
    resp = asyncio.run(server.termdat_get_concept(TermdatGetConceptInput(concept="abc")))
    assert resp.match_type == "none"
    assert "Ungültige TERMDAT-Referenz" in resp.markdown


@pytest.mark.parametrize("raw,expected", [
    ("40109", "40109"),
    ("https://register.ld.admin.ch/termdat/40109", "40109"),
    ("https://register.ld.admin.ch/termdat/40109/3/de", "40109"),
    ("https://www.termdat.bk.admin.ch/entry/40109", "40109"),
    ("not-an-id", None),
])
def test_termdat_concept_id_normalisation(raw: str, expected: str | None) -> None:
    assert server.termdat_concept_id(raw) == expected


# --- Quirk 1: status vs. deadline conflict ---------------------------------

@respx.mock
@pytest.mark.asyncio
async def test_quirk1_status_running_but_deadline_past_flags_conflict() -> None:
    # Status «Laufend» (/2), aber Frist längst abgelaufen → status_conflict.
    respx.get(ENDPOINT).mock(return_value=_sparql_response([
        _binding(c=CONS_URI, title="Alte Vorlage", status=server.CONSULTATION_STATUS_RUNNING,
                 start="2019-01-01", end="2020-01-01", instLabel="Departement"),
    ]))
    resp = await server.fedlex_get_consultation(GetConsultationInput(event_id="proj/2026/71/cons_1"))
    assert resp.results[0]["status_conflict"] is True
    assert "status_conflict" in resp.markdown


def test_deadline_status_pure_date_wins() -> None:
    """Zentrale Fristenlogik: die Frist gewinnt über das Quell-Statusfeld."""
    running = consultations.CONSULTATION_STATUS_RUNNING
    closed = consultations.CONSULTATION_STATUS_BASE + "5"
    today = date(2026, 7, 20)

    # Quelle «Laufend», Frist abgelaufen → abgeleitet «Abgeschlossen», Konflikt.
    status, is_open, conflict = consultations.deadline_status(date(2020, 1, 1), running, today)
    assert (status, is_open, conflict) == (consultations.DERIVED_CLOSED, False, True)

    # Quelle «Laufend», Frist künftig → «Laufend», kein Konflikt.
    status, is_open, conflict = consultations.deadline_status(date(2099, 1, 1), running, today)
    assert (status, is_open, conflict) == (consultations.DERIVED_RUNNING, True, False)

    # Quelle «Abgeschlossen», Frist künftig → «Laufend» (Datum gewinnt), Konflikt.
    status, is_open, conflict = consultations.deadline_status(date(2099, 1, 1), closed, today)
    assert (status, is_open, conflict) == (consultations.DERIVED_RUNNING, True, True)

    # Keine Frist → Rückfall auf Quell-Label, is_open False, kein Konflikt.
    status, is_open, conflict = consultations.deadline_status(None, running, today)
    assert (status, is_open, conflict) == ("Laufend", False, False)


def test_days_until_pure_calendar_semantics() -> None:
    today = date(2026, 7, 20)
    assert consultations.days_until(date(2026, 7, 25), today) == 5
    assert consultations.days_until(date(2026, 7, 20), today) == 0   # Frist heute
    assert consultations.days_until(date(2026, 7, 19), today) == -1  # gestern abgelaufen
    assert consultations.days_until(None, today) is None


# --- Quirk: consultation without hasSubTask --------------------------------

@respx.mock
@pytest.mark.asyncio
async def test_consultation_without_subtask_returns_null_deadline() -> None:
    respx.get(ENDPOINT).mock(return_value=_sparql_response([
        _binding(c=CONS_URI, title="Ohne Teilaufgabe",
                 status=server.CONSULTATION_STATUS_BASE + "1"),
    ]))
    resp = await server.fedlex_get_consultation(GetConsultationInput(event_id="proj/2026/71/cons_1"))
    assert resp.match_type == "exact"
    assert resp.results[0]["deadline"] is None
    assert resp.results[0]["status_conflict"] is False
    assert "keine Teilaufgabe" in resp.markdown


# --- Retry on transient 503 -------------------------------------------------

@respx.mock
@pytest.mark.asyncio
async def test_retry_on_503_then_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "RETRY_BASE_DELAY", 0)
    respx.get(ENDPOINT).mock(side_effect=[
        httpx.Response(503, text="temporarily unavailable"),
        _sparql_response([_open_cons_binding("2099-09-01")]),
    ])
    resp = await server.fedlex_get_open_consultations(GetOpenConsultationsInput())
    assert resp.match_type == "exact"
    assert resp.count == 1


@respx.mock
@pytest.mark.asyncio
async def test_retry_on_503_lindas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "RETRY_BASE_DELAY", 0)
    respx.get(LINDAS).mock(side_effect=[
        httpx.Response(503),
        _sparql_response([_binding(s="https://register.ld.admin.ch/termdat/40109/3/de",
                                   name="Volksschule")]),
        _sparql_response([_binding(c="https://register.ld.admin.ch/termdat/40109",
                                   name="obligatorische Schule", nl="de")]),
    ])
    resp = await server.termdat_lookup_term(TermdatLookupInput(term="Volksschule"))
    assert resp.count == 1


@respx.mock
@pytest.mark.asyncio
async def test_400_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "RETRY_BASE_DELAY", 0)
    route = respx.get(ENDPOINT).mock(return_value=httpx.Response(400, text="bad"))
    resp = await server.fedlex_get_open_consultations(GetOpenConsultationsInput())
    assert resp.match_type == "error"
    assert route.call_count == 1  # 400 ist deterministisch → kein Retry


# --- Timeout / network error → clean masked error ---------------------------

@respx.mock
@pytest.mark.asyncio
async def test_lindas_timeout_masked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "RETRY_BASE_DELAY", 0)
    respx.get(LINDAS).mock(side_effect=httpx.TimeoutException("slow"))
    resp = await server.termdat_lookup_term(TermdatLookupInput(term="Volksschule"))
    assert resp.match_type == "error"
    assert "TERMDAT (LINDAS)" in resp.markdown
    assert "slow" not in resp.markdown


# --- Isolation: LINDAS down, fedlex_* still works ---------------------------

@respx.mock
@pytest.mark.asyncio
async def test_isolation_lindas_down_fedlex_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "RETRY_BASE_DELAY", 0)
    respx.get(LINDAS).mock(side_effect=httpx.ConnectError("lindas down"))
    respx.get(ENDPOINT).mock(return_value=_sparql_response([_open_cons_binding("2099-09-01")]))

    termdat = await server.termdat_lookup_term(TermdatLookupInput(term="Volksschule"))
    assert termdat.match_type == "error"  # LINDAS ist unten

    fedlex = await server.fedlex_get_open_consultations(GetOpenConsultationsInput())
    assert fedlex.match_type == "exact"  # Fedlex funktioniert unbeeinträchtigt weiter
    assert fedlex.count == 1


# --- SPARQL escaping: quote/backslash must not break the query --------------

@respx.mock
@pytest.mark.asyncio
async def test_termdat_escaping_quote_backslash() -> None:
    captured: dict = {}

    def _capture(request: httpx.Request) -> httpx.Response:
        captured["query"] = request.url.params.get("query")
        return _sparql_response([])

    respx.get(LINDAS).mock(side_effect=_capture)
    # KEYWORD_PATTERN erlaubt keine " oder \, daher über das reine Escaping prüfen:
    assert sparql_escape('foo" \\ bar') == 'foo\\" \\\\ bar'
    resp = await server.termdat_lookup_term(TermdatLookupInput(term="Datenschutz"))
    assert resp.match_type == "none"
    assert 'FILTER(LCASE(STR(?name)) = "datenschutz")' in captured["query"]


def test_keyword_pattern_still_rejects_injection_in_consultations() -> None:
    with pytest.raises(ValidationError):
        GetOpenConsultationsInput(keyword='x" } INJECT')
    with pytest.raises(ValidationError):
        TermdatLookupInput(term='x" } INJECT')


def test_event_id_pattern_rejects_malformed() -> None:
    with pytest.raises(ValidationError):
        GetConsultationInput(event_id="proj/2026/71")  # kein cons_N
    assert GetConsultationInput(event_id="proj/2026/71/cons_1").event_id == "proj/2026/71/cons_1"


# --- Wiring for the two isolated clients ------------------------------------

def test_lindas_client_default_is_none_outside_lifespan() -> None:
    assert server._lindas_client is None


def test_lindas_host_on_egress_allow_list() -> None:
    assert server.LINDAS_HOST in server.ALLOWED_EGRESS_HOSTS
    server.assert_host_allowed(server.LINDAS_ENDPOINT)  # no raise


# ===========================================================================
# Fristenlogik mit fixiertem «heute» (injizierbare Uhr statt Systemzeit)
# ===========================================================================
# Alle Tools lesen «heute» über server.today_in_zurich(); der Fixture friert
# diese Referenz ein, damit days_remaining/Status deterministisch prüfbar sind.

FROZEN_TODAY = date(2026, 7, 20)


@pytest.fixture
def frozen_today(monkeypatch: pytest.MonkeyPatch) -> date:
    monkeypatch.setattr(server, "today_in_zurich", lambda: FROZEN_TODAY)
    return FROZEN_TODAY


@respx.mock
@pytest.mark.asyncio
async def test_open_running_has_correct_days_remaining(frozen_today: date) -> None:
    # Pflichtfall 1: laufende Vernehmlassung → korrektes days_remaining.
    respx.get(ENDPOINT).mock(return_value=_sparql_response([_open_cons_binding("2026-07-25")]))
    resp = await server.fedlex_get_open_consultations(GetOpenConsultationsInput())
    r = resp.results[0]
    assert r["days_remaining"] == 5
    assert r["status"] == "Laufend"
    assert r["is_open"] is True
    assert "days_remaining" in resp.markdown


@respx.mock
@pytest.mark.asyncio
async def test_deadline_today_is_open_zero_days(frozen_today: date) -> None:
    # Pflichtfall 3: Frist heute → laufend, days_remaining == 0.
    respx.get(ENDPOINT).mock(return_value=_sparql_response([_open_cons_binding("2026-07-20")]))
    resp = await server.fedlex_get_open_consultations(GetOpenConsultationsInput())
    r = resp.results[0]
    assert r["days_remaining"] == 0
    assert r["status"] == "Laufend"
    assert r["is_open"] is True


@respx.mock
@pytest.mark.asyncio
async def test_deadline_yesterday_closed_and_date_wins(frozen_today: date) -> None:
    # Pflichtfälle 2 & 4: Frist gestern abgelaufen, Quelle meldet «Laufend» →
    # Status «Abgeschlossen» (Datum gewinnt), Diskrepanz ausgewiesen.
    respx.get(ENDPOINT).mock(return_value=_sparql_response([
        _binding(c=CONS_URI, title="Abgelaufene Vorlage",
                 status=server.CONSULTATION_STATUS_RUNNING, start="2026-05-01", end="2026-07-19",
                 instLabel="Departement"),
    ]))
    resp = await server.fedlex_get_consultation(GetConsultationInput(event_id="proj/2026/71/cons_1"))
    r = resp.results[0]
    assert r["status"] == "Abgeschlossen"       # Datum gewinnt, nicht «Laufend»
    assert r["status_source"] == "Laufend"      # rohes Quell-Label bleibt sichtbar
    assert r["days_remaining"] == -1
    assert r["is_open"] is False
    assert r["status_conflict"] is True
    assert "status_conflict" in resp.markdown


@respx.mock
@pytest.mark.asyncio
async def test_open_query_excludes_expired_and_dedupes_language(frozen_today: date) -> None:
    # Pflichtfall 2 (Kern): abgelaufene Verfahren dürfen gar nicht erst in der
    # Liste der laufenden erscheinen — die SPARQL-Frist-Grenze filtert sie weg.
    # Pflichtfall 6: der Sprachfilter entfernt die DE/FR/IT-Dreifach-Duplikate.
    captured: dict = {}

    def _capture(request: httpx.Request) -> httpx.Response:
        captured["query"] = request.url.params.get("query")
        return _sparql_response([])

    respx.get(ENDPOINT).mock(side_effect=_capture)
    await server.fedlex_get_open_consultations(GetOpenConsultationsInput())
    q = captured["query"]
    assert 'xsd:date(?end) >= "2026-07-20"^^xsd:date' in q  # Frist-Grenze = heute
    assert 'FILTER(LANG(?title) = "de")' in q               # Sprach-Dedupe


@respx.mock
@pytest.mark.asyncio
async def test_topic_education_finds_known_template_and_discloses_strategy(frozen_today: date) -> None:
    # Pflichtfall 5: Themenfilter findet eine bekannte Bildungsvorlage; die
    # verwendete Stichwortstrategie wird in der Antwort ausgewiesen.
    respx.get(ENDPOINT).mock(return_value=_sparql_response([
        _open_cons_binding("2026-09-01", title="Totalrevision Berufsbildungsgesetz"),
    ]))
    resp = await server.fedlex_get_open_consultations(
        GetOpenConsultationsInput(topic="education")
    )
    assert resp.count == 1
    assert "Berufsbildungsgesetz" in resp.markdown
    assert "Themenfilter" in resp.markdown
    assert "berufsbildung" in resp.message  # ausgewiesene Begriffs-Union


@respx.mock
@pytest.mark.asyncio
async def test_open_consultations_endpoint_unreachable_explains(frozen_today: date,
                                                                monkeypatch: pytest.MonkeyPatch) -> None:
    # Pflichtfall 7: Endpoint nicht erreichbar → erklärender Fehler, kein leeres
    # (fälschlich beruhigendes) Resultat.
    monkeypatch.setattr(server, "RETRY_BASE_DELAY", 0)
    respx.get(ENDPOINT).mock(side_effect=httpx.ConnectError("network down"))
    resp = await server.fedlex_get_open_consultations(GetOpenConsultationsInput())
    assert resp.match_type == "error"          # NICHT "none"
    assert "Verbindung zu Fedlex" in resp.markdown
    assert "network down" not in resp.markdown


def test_consultation_model_has_mandatory_fields() -> None:
    """Das typisierte Modell führt alle spezifizierten Pflichtfelder."""
    required = {
        "title", "status", "opened_on", "deadline", "days_remaining",
        "lead_office", "source_url", "retrieved_at", "language",
    }
    assert required <= set(consultations.Consultation.model_fields)


# ---------------------------------------------------------------------------
# Live smoke test (skipped in CI via: pytest -m 'not live')
# ---------------------------------------------------------------------------

@pytest.mark.live
@pytest.mark.asyncio
async def test_live_sparql_endpoint() -> None:
    resp = await server.fedlex_get_law_by_sr(GetLawBySrInput(sr_number="101", language=Language.DE))
    assert "101" in resp.markdown


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_open_consultations() -> None:
    resp = await server.fedlex_get_open_consultations(GetOpenConsultationsInput(limit=5))
    assert resp.match_type in ("exact", "none")
    assert resp.source == server.ATTRIBUTION_FEDLEX


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_termdat_lookup() -> None:
    resp = await server.termdat_lookup_term(
        TermdatLookupInput(term="Volksschule", target_languages=["fr", "it"])
    )
    assert "Partial dataset" in resp.markdown
