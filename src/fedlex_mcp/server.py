"""
Fedlex MCP Server
=================
MCP server für das Schweizer Bundesrecht via den Fedlex SPARQL-Endpoint.
Ermöglicht Zugriff auf die Systematische Rechtssammlung (SR), Amtliche
Sammlung (AS), Bundesblatt (BBl) und Staatsverträge.

Ab v1.1.0 zusätzlich abgedeckt (beide ebenfalls SPARQL-basiert):
  - Vernehmlassungen (jolux:Consultation) über denselben Fedlex-Endpoint
  - TERMDAT, die Terminologiedatenbank der Bundeskanzlei, über den separaten
    LINDAS-Endpoint (lindas.admin.ch/query, Graph fch/termdat)

Isolationspflicht (ARCH A): Fedlex und LINDAS sind getrennte Endpoints mit
getrennten httpx-Clients und Timeouts. Ein LINDAS-Ausfall darf die fedlex_*-
Tools nicht beeinträchtigen und umgekehrt.

Datenquelle: https://fedlex.data.admin.ch  ·  https://lindas.admin.ch/fch/termdat
Lizenz: Freie Wiederverwendung gemäss fedlex.admin.ch/de/broadcasters

JOLux-Datenmodell (verifiziert):
  - jolux:ConsolidationAbstract  →  SR-Eintrag (Abstract über alle Versionen)
    └─ jolux:isRealizedBy  →  jolux:Expression (sprachspez. Fassung)
       ├─ jolux:title               Vollständiger Titel
       ├─ jolux:titleShort          Abkürzung (z.B. "DSG", "BV")
       └─ jolux:historicalLegalId   SR-Nummer (z.B. "235.1")
  - jolux:Act  →  Einzelpublikation in AS (eli/oc/) oder BBl (eli/fga/)
  - jolux:inForceStatus:
       .../0  In Kraft
       .../1  Nicht mehr in der SR publiziert
       .../3  Nicht mehr in Kraft

Transport: Dual — stdio (lokal) und Streamable HTTP (Cloud/Render.com),
wählbar über die Umgebungsvariable FEDLEX_TRANSPORT (stdio | streamable-http).

MCP Protocol Version: ausgehandelt vom mcp-SDK (>=1.3.0); siehe README-Sektion
"MCP Protocol Version".
"""

import hashlib
import json
import os
import re
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from typing import Any, Literal

import httpx
import structlog
from mcp.server.mcpserver import Context, MCPServer
from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from . import consultations, sparql_client

# ---------------------------------------------------------------------------
# Konstanten
# ---------------------------------------------------------------------------

SPARQL_ENDPOINT = "https://fedlex.data.admin.ch/sparqlendpoint"
FEDLEX_BASE_URL = "https://www.fedlex.admin.ch"
FEDLEX_DATA_HOST = "fedlex.data.admin.ch"
REQUEST_TIMEOUT = 45
MAX_RESULTS_DEFAULT = 20
MAX_RESULTS_LIMIT = 100

# TERMDAT via LINDAS — bewusst ein SEPARATER Endpoint mit eigenem Client und
# eigenem Timeout (Isolationspflicht, ARCH A). Ein LINDAS-Ausfall darf die
# fedlex_*-Tools nicht beeinträchtigen.
LINDAS_ENDPOINT = "https://lindas.admin.ch/query"
LINDAS_HOST = "lindas.admin.ch"
LINDAS_GRAPH = "https://lindas.admin.ch/fch/termdat"
LINDAS_TIMEOUT = 45
TERMDAT_TERM_TYPE = "https://schema.ld.admin.ch/Term"
TERMDAT_REGISTER_BASE = "https://register.ld.admin.ch/termdat"
# Reality-Check-Diskrepanz (Quirk 2): die Bundeskanzlei kommuniziert ~400'000
# TERMDAT-Einträge, als Linked Data auf LINDAS liegen jedoch nur rund 77'692.
TERMDAT_LINDAS_ENTRIES = 77_692
TERMDAT_COMMUNICATED_ENTRIES = 400_000

SOURCE_NAME = "Fedlex, Schweizerische Bundeskanzlei (fedlex.admin.ch)"
SOURCE_LICENSE = "Freie Wiederverwendung gemäss fedlex.admin.ch/de/broadcasters"
TERMDAT_SOURCE_NAME = "TERMDAT, Schweizerische Bundeskanzlei — via LINDAS (lindas.admin.ch/fch/termdat)"
TERMDAT_LICENSE = "Open reuse licence (opendata.swiss / LINDAS)"

# Attribution-Strings. Der TERMDAT-Hinweis auf den publizierten Teilbestand
# gehört in JEDE TERMDAT-Response (nicht nur ins README), damit das Modell aus
# einem negativen Treffer nicht schliesst, der Begriff fehle in TERMDAT.
ATTRIBUTION_FEDLEX = "Data: Fedlex / Swiss Federal Chancellery — open reuse licence."
ATTRIBUTION_TERMDAT = (
    "Data: TERMDAT / Swiss Federal Chancellery, Terminology Section, "
    "via LINDAS (lindas.admin.ch/fch/termdat). "
    "Partial dataset: 77,692 of ~400,000 entries published as Linked Data."
)

# Defense-in-depth: der Server spricht ausschliesslich diese Endpoints an
# (SEC-021 Egress-Allow-List auf Code-Ebene). LINDAS ist bewusst getrennt
# gelistet — sein Ausfall isoliert (siehe run_lindas / _lindas_client).
ALLOWED_EGRESS_HOSTS = frozenset({FEDLEX_DATA_HOST, LINDAS_HOST})

# Retry-Parameter für den geteilten SPARQL-Client (siehe sparql_client). 400/404
# sind bewusst nicht retrybar (deterministisch). Werte werden pro Aufruf an
# sparql_client übergeben; Tests monkeypatchen RETRY_BASE_DELAY auf 0.
RETRY_MAX_ATTEMPTS = sparql_client.DEFAULT_MAX_ATTEMPTS
RETRY_BASE_DELAY = sparql_client.DEFAULT_BASE_DELAY  # Sekunden. Tests setzen 0.

# Whitelist-Pattern für Freitext-Suchbegriffe (SEC-018). Erlaubt Buchstaben
# (inkl. Umlaute/Akzente via Unicode-\w), Ziffern, Leerzeichen und gängige
# Interpunktion — aber keine Anführungszeichen, Backslashes oder geschweiften
# Klammern, mit denen man aus einem SPARQL-Literal ausbrechen könnte.
KEYWORD_PATTERN = r"^[\w\s.\-'’(),:/&+]+$"
# SR-Nummern: nur Zifferngruppen, durch Punkte getrennt (z.B. 101, 235.1, 0.101).
SR_NUMBER_PATTERN = r"^\d{1,3}(\.\d+)*$"

LANG_SUFFIX = {"de": "/de", "fr": "/fr", "it": "/it", "rm": "/rm"}

STATUS_IN_FORCE = "https://fedlex.data.admin.ch/vocabulary/enforcement-status/0"
STATUS_NOT_PUBLISHED = "https://fedlex.data.admin.ch/vocabulary/enforcement-status/1"
STATUS_NO_LONGER_FORCE = "https://fedlex.data.admin.ch/vocabulary/enforcement-status/3"

STATUS_LABELS = {
    STATUS_IN_FORCE: "✅ In Kraft",
    STATUS_NOT_PUBLISHED: "⚠️ Nicht mehr in SR publiziert",
    STATUS_NO_LONGER_FORCE: "❌ Nicht mehr in Kraft",
}

# Vernehmlassungs-Status-Vokabular und -Logik liegen in der isolierten
# consultations-Schicht (getrennt von der SR-/AS-/BBl-Schicht). Hier nur
# re-exportiert, damit bestehende Referenzen (`server.CONSULTATION_STATUS_*`)
# stabil bleiben. Verifiziert live am 18.07.2026 gegen
# .../vocabulary/consultation-status/.
CONSULTATION_STATUS_BASE = consultations.CONSULTATION_STATUS_BASE
CONSULTATION_STATUS_RUNNING = consultations.CONSULTATION_STATUS_RUNNING
CONSULTATION_STATUS_LABELS = consultations.CONSULTATION_STATUS_LABELS
CONSULTATION_STATUS_ALIASES = consultations.CONSULTATION_STATUS_ALIASES
# Zentrale Europe/Zurich-Uhr (zur Laufzeit; Tests monkeypatchen diese Referenz).
today_in_zurich = consultations.today_in_zurich

# eventId einer Vernehmlassung, z.B. "proj/2026/71/cons_1". Strikte Whitelist,
# damit nichts Injizierbares in ein SPARQL-Literal gelangt (SEC-018).
EVENT_ID_PATTERN = r"^proj/\d{4}/\d+/cons_\d+$"
# TERMDAT-Eingabe: entweder eine reine ID (40109), eine Konzept-/Term-URI unter
# register.ld.admin.ch/termdat/… oder die termdat.bk.admin.ch/entry/…-Form.
# Nur unkritische Zeichen erlaubt; die numerische ID wird ohnehin serverseitig
# extrahiert und die URI selbst konstruiert (injektionssicher).
TERMDAT_INPUT_PATTERN = r"^[0-9A-Za-z:/._\-]+$"

FEDLEX_SOURCE = f"\n---\n*Quelle: {SOURCE_NAME}*"
TERMDAT_SOURCE = f"\n---\n*{ATTRIBUTION_TERMDAT}*"

# ---------------------------------------------------------------------------
# Strukturiertes Logging (OBS-003)
# ---------------------------------------------------------------------------
# JSON-Logs gehen bewusst auf STDERR — bei stdio-Transport ist STDOUT exklusiv
# für das JSON-RPC-Protokoll reserviert (OBS-004).

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.WriteLoggerFactory(file=sys.stderr),
    cache_logger_on_first_use=True,
)
log = structlog.get_logger("fedlex_mcp")

# ---------------------------------------------------------------------------
# Optionales OpenTelemetry-Tracing (OBS-006)
# ---------------------------------------------------------------------------
# Wird nur aktiviert, wenn OTEL_EXPORTER_OTLP_ENDPOINT gesetzt ist UND die
# opentelemetry-Pakete installiert sind (optional extra: pip install
# 'fedlex-mcp[otel]'). Ohne Konfiguration ein vollständiger No-Op.

_tracer: Any = None


def _init_tracing() -> None:
    global _tracer
    if _tracer is not None:
        return
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        log.warning("otel_requested_but_packages_missing", hint="pip install 'fedlex-mcp[otel]'")
        return

    provider = TracerProvider(
        resource=Resource.create({
            "service.name": "fedlex-mcp",
            "deployment.environment": os.environ.get("FEDLEX_ENV", "production"),
        })
    )
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    # Auto-Instrumentierung: jeder SPARQL-HTTP-Call wird ein Child-Span.
    HTTPXClientInstrumentor().instrument()
    _tracer = trace.get_tracer("fedlex_mcp")
    log.info("tracing_enabled", endpoint=endpoint)


@asynccontextmanager
async def _tool_span(tool: str, **attrs: object) -> AsyncIterator[None]:
    """Erzeugt — falls Tracing aktiv ist — einen Span pro Tool-Call (OBS-006).

    Sensible Daten (freier Args-Inhalt) werden bewusst NICHT als Attribut
    gesetzt; nur Tool-Name und unkritische Metadaten (Sprache, Limits, Flags).
    """
    if _tracer is None:
        yield
        return
    with _tracer.start_as_current_span(f"mcp.tool.{tool}") as span:
        span.set_attribute("mcp.tool.name", tool)
        for key, value in attrs.items():
            if value is not None and isinstance(value, (str, int, float, bool)):
                span.set_attribute(f"mcp.{key}", value)
        yield


# ---------------------------------------------------------------------------
# Konfiguration (Settings statt globaler Module-Vars — ARCH-004)
# ---------------------------------------------------------------------------


class Settings(BaseSettings):
    """Laufzeit-Konfiguration, vollständig über Env-Vars steuerbar.

    Transport-Wahl, Host/Port und CORS-Origins kommen aus der Umgebung, damit
    derselbe Code lokal (stdio) und in der Cloud (streamable-http) läuft, ohne
    Code-Fork.
    """

    model_config = SettingsConfigDict(env_prefix="FEDLEX_", extra="ignore")

    transport: str = "stdio"  # stdio | streamable-http
    host: str = "127.0.0.1"
    port: int = 8000
    # Kommagetrennte Origin-Liste; in Produktion explizit setzen, kein "*".
    allowed_origins: str = "http://localhost,http://127.0.0.1"
    # SEC-005, eingehend: Hostnamen, unter denen dieser Server erreichbar ist.
    # Nötig für die Host/Origin-Prüfung des Transports, sobald nicht auf Loopback
    # gebunden wird — der Prozess kann den Service-/DNS-Namen nicht erraten.
    allowed_hosts: str = ""


settings = Settings()

# ---------------------------------------------------------------------------
# Geteilte Infrastruktur
# ---------------------------------------------------------------------------


class Language(StrEnum):
    """Offizielle Landessprachen der Schweizerischen Eidgenossenschaft."""

    DE = "de"
    FR = "fr"
    IT = "it"
    RM = "rm"


class FedlexResponse(BaseModel):
    """Einheitlicher Response-Envelope für alle Tools (SDK-002).

    `markdown` enthält die menschenlesbare Aufbereitung; `results` die
    strukturierten Datensätze (jeder mit Provenance: `uri` + `url`). Quelle und
    Lizenz sind explizit (CH-004).
    """

    source: str = SOURCE_NAME
    license: str = SOURCE_LICENSE
    tool: str
    match_type: Literal["exact", "none", "error"]
    count: int
    results: list[dict]
    markdown: str
    message: str | None = None


@dataclass
class AppContext:
    """Über den Lifespan geteilte Ressourcen.

    Zwei getrennte Clients erfüllen die Isolationspflicht (ARCH A): Fedlex und
    LINDAS teilen sich weder Connection-Pool noch Timeout, damit ein hängender
    Endpoint den jeweils anderen nicht ausbremst.
    """

    client: httpx.AsyncClient
    lindas_client: httpx.AsyncClient


# Über den Server-Lifecycle geteilte HTTP-Clients (SDK-001) — je einer pro
# Endpoint, im Lifespan erstellt und sauber geschlossen (kein Client pro Call).
_http_client: httpx.AsyncClient | None = None
_lindas_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(_server: MCPServer) -> AsyncIterator[AppContext]:
    """Erstellt die geteilten HTTP-Clients (Fedlex + LINDAS) und schliesst sie."""
    global _http_client, _lindas_client
    _init_tracing()
    async with (
        httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client,
        httpx.AsyncClient(timeout=LINDAS_TIMEOUT) as lindas_client,
    ):
        _http_client = client
        _lindas_client = lindas_client
        log.info(
            "lifespan_start",
            shared_http_client=True,
            isolated_lindas_client=True,
            tracing=_tracer is not None,
        )
        try:
            yield AppContext(client=client, lindas_client=lindas_client)
        finally:
            _http_client = None
            _lindas_client = None
            log.info("lifespan_stop")


async def _trace(ctx: Context | None, tool: str, **fields: object) -> None:
    """Loggt einen Tool-Aufruf strukturiert (OBS-003) und — falls ein MCP-Context
    vorhanden ist — auch an den Client zurück (SDK-003)."""
    log.info("tool_call", tool=tool, **fields)
    if ctx is not None:
        try:
            await ctx.info(f"{tool}: Anfrage an Fedlex SPARQL")
        except Exception:  # pragma: no cover - Context ohne aktive Session
            pass


def _ok(tool: str, results: list[dict], markdown: str,
        match_type: Literal["exact", "none"] = "exact",
        source: str = SOURCE_NAME, license: str = SOURCE_LICENSE,
        message: str | None = None) -> FedlexResponse:
    return FedlexResponse(
        source=source, license=license, tool=tool, match_type=match_type,
        count=len(results), results=results, markdown=markdown, message=message,
    )


def _empty(tool: str, markdown: str, source: str = SOURCE_NAME,
           license: str = SOURCE_LICENSE, message: str | None = None) -> FedlexResponse:
    return FedlexResponse(
        source=source, license=license, tool=tool, match_type="none",
        count=0, results=[], markdown=markdown, message=message,
    )


async def _fail(ctx: Context | None, tool: str, e: Exception, *,
                service: str = "Fedlex", source: str = SOURCE_NAME,
                license: str = SOURCE_LICENSE) -> FedlexResponse:
    """Einheitlicher Fehler-Pfad: maskierte Meldung + ctx.error (SDK-003 / OBS-002)."""
    msg = handle_error(tool, e, service=service)
    if ctx is not None:
        try:
            await ctx.error(msg)
        except Exception:  # pragma: no cover - Context ohne aktive Session
            pass
    return FedlexResponse(
        source=source, license=license, tool=tool, match_type="error",
        count=0, results=[], markdown=msg, message=msg,
    )


# Aus dem wiederverwendbaren Modul re-exportiert (SEC-004 / SEC-018,
# Defense-in-Depth zusätzlich zur Pydantic-Pattern-Validierung).
sparql_escape = sparql_client.sparql_escape


def assert_host_allowed(url: str) -> None:
    """Prüft vor jedem ausgehenden Request, dass der Ziel-Host auf der
    Code-Layer-Egress-Allow-List steht (SEC-021 / SEC-005 Defense-in-Depth)."""
    host = httpx.URL(url).host
    if host not in ALLOWED_EGRESS_HOSTS:
        raise PermissionError(f"Egress zu Host '{host}' ist nicht erlaubt")


async def run_sparql(query: str, client: httpx.AsyncClient | None = None) -> list[dict]:
    """Führt SPARQL-Abfrage gegen den Fedlex-Endpoint aus, gibt Bindings zurück.

    Nutzt standardmässig den über den Lifespan geteilten Client. Fällt nur dann
    auf einen Ad-hoc-Client zurück, wenn kein Lifespan aktiv ist (z.B. in
    isolierten Skripten/Tests).
    """
    active = client or _http_client
    if active is not None:
        return await _execute_sparql(active, SPARQL_ENDPOINT, query)
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as tmp:
        return await _execute_sparql(tmp, SPARQL_ENDPOINT, query)


async def run_lindas(query: str, client: httpx.AsyncClient | None = None) -> list[dict]:
    """Führt SPARQL-Abfrage gegen den LINDAS-Endpoint (TERMDAT) aus.

    Nutzt bewusst einen EIGENEN Client (_lindas_client) mit eigenem Timeout —
    Isolation gegenüber Fedlex (ARCH A). Ein LINDAS-Ausfall bleibt hier lokal
    und erreicht die fedlex_*-Tools nicht.
    """
    active = client or _lindas_client
    if active is not None:
        return await _execute_sparql(active, LINDAS_ENDPOINT, query)
    async with httpx.AsyncClient(timeout=LINDAS_TIMEOUT) as tmp:
        return await _execute_sparql(tmp, LINDAS_ENDPOINT, query)


def _log_sparql_retry(attempt: int, endpoint: str, exc: Exception) -> None:
    """Retry-Callback für den geteilten Client (bewahrt das bisherige Logging)."""
    log.info("sparql_retry", endpoint=endpoint, attempt=attempt, error_type=type(exc).__name__)


async def _execute_sparql(client: httpx.AsyncClient, endpoint: str, query: str) -> list[dict]:
    """Sendet die Query an `endpoint` und gibt die Bindings zurück.

    Dünne Bindung an den geteilten `sparql_client` (Egress-Guard, Retry nur bei
    transienten Fehlern, exponentielles Backoff; deterministische 4xx sofort).
    `RETRY_BASE_DELAY` wird zur Laufzeit gelesen (Tests monkeypatchen).
    """
    return await sparql_client.get_bindings(
        client,
        endpoint,
        query,
        base_delay=RETRY_BASE_DELAY,
        max_attempts=RETRY_MAX_ATTEMPTS,
        egress_check=assert_host_allowed,
        on_retry=_log_sparql_retry,
    )


# SPARQL-Helfer aus dem wiederverwendbaren Modul (Rückwärtskompatibilität).
val = sparql_client.binding_val


def fedlex_url(uri: str, lang: str = "de") -> str:
    """Wandelt Fedlex-Daten-URI in lesbare fedlex.admin.ch-URL um."""
    if uri.startswith("https://fedlex.data.admin.ch/"):
        path = uri.replace("https://fedlex.data.admin.ch", "")
        return f"{FEDLEX_BASE_URL}{path}/{lang}"
    return uri


def status_label(status_uri: str) -> str:
    """Gibt lesbares Label für einen Enforcement-Status-URI zurück."""
    return STATUS_LABELS.get(status_uri, f"({status_uri.split('/')[-1]})")


def handle_error(tool: str, e: Exception, service: str = "Fedlex") -> str:
    """Einheitliche, handlungsweisende Fehlermeldungen.

    `service` benennt den betroffenen Endpoint ("Fedlex" oder "TERMDAT (LINDAS)"),
    damit das Modell bei einem isolierten LINDAS-Ausfall nicht auf einen
    Fedlex-Fehler schliesst. Interne Exception-Details werden ausschliesslich
    serverseitig geloggt und nie an das LLM zurückgegeben (OBS-001 / OBS-002).
    """
    log.warning("tool_error", tool=tool, service=service,
                error_type=type(e).__name__, detail=str(e))
    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        if code == 400:
            return "Fehler: Ungültige SPARQL-Abfrage (HTTP 400). Suchparameter überprüfen."
        if code == 429:
            return "Fehler: Rate Limit erreicht. Bitte kurz warten und erneut versuchen."
        if code == 503:
            return f"Fehler: {service} vorübergehend nicht verfügbar. Später erneut versuchen."
        return f"Fehler: HTTP {code} vom {service}-Endpoint."
    if isinstance(e, (httpx.TimeoutException, httpx.ReadTimeout)):
        return (
            f"Fehler: Timeout beim {service}-Endpoint. "
            "Komplexe SPARQL-Abfragen können länger dauern — bitte erneut versuchen."
        )
    if isinstance(e, httpx.ConnectError):
        return f"Fehler: Verbindung zu {service} fehlgeschlagen. Internetverbindung prüfen."
    return f"Fehler: Unerwarteter Fehler beim Abruf vom {service}-Endpoint. Bitte erneut versuchen."


def result_header(count: int, desc: str) -> str:
    """Standardisierter Ergebnisheader."""
    return f"## Fedlex — {desc}\n**Treffer:** {count}\n\n"


def no_match_hint(tips: str) -> str:
    """Maschinenlesbarer Hinweis bei leeren Resultaten (ARCH-003): markiert den
    match_type explizit, damit das LLM nicht halluziniert, sondern verfeinert."""
    return f"\n\n_(match_type: none — keine Treffer)_\n\n{tips}"


# ---------------------------------------------------------------------------
# Server-Initialisierung
# ---------------------------------------------------------------------------

mcp = MCPServer(
    "fedlex_mcp",
    instructions=(
        "MCP-Server für das Schweizer Bundesrecht (Fedlex). "
        "Zugriff auf die Systematische Rechtssammlung (SR), "
        "Amtliche Sammlung (AS), Bundesblatt (BBl) und Staatsverträge. "
        "Alle Daten stammen vom SPARQL-Endpoint der Schweizerischen Bundeskanzlei. "
        "Tools liefern einen strukturierten Envelope (results + markdown)."
    ),
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Input-Modelle
# ---------------------------------------------------------------------------


class SearchLawsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    keywords: str = Field(
        ...,
        description="Suchbegriff(e) im Erlasstittel, z.B. 'Volksschule', 'Datenschutz', 'Berufsbildung'",
        min_length=2, max_length=200, pattern=KEYWORD_PATTERN,
    )
    language: Language = Field(default=Language.DE, description="Sprache: 'de', 'fr', 'it', 'rm'")
    in_force_only: bool = Field(default=True, description="Nur gültige Erlasse (Standard: True)")
    limit: int = Field(default=MAX_RESULTS_DEFAULT, ge=1, le=MAX_RESULTS_LIMIT,
                       description=f"Maximale Trefferzahl (1–{MAX_RESULTS_LIMIT})")


class GetLawBySrInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    sr_number: str = Field(
        ...,
        description="SR-Nummer, z.B. '101' (BV), '235.1' (DSG), '412.10' (BBG), '170.32' (VG)",
        min_length=1, max_length=20, pattern=SR_NUMBER_PATTERN,
    )
    language: Language = Field(default=Language.DE)


class GetRecentPublicationsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    days: int = Field(default=30, ge=1, le=365, description="Letzte N Tage (Standard: 30)")
    language: Language = Field(default=Language.DE)
    limit: int = Field(default=MAX_RESULTS_DEFAULT, ge=1, le=MAX_RESULTS_LIMIT)


class GetUpcomingChangesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    days_ahead: int = Field(default=90, ge=1, le=365, description="Vorausschau in Tagen (Standard: 90)")
    language: Language = Field(default=Language.DE)
    limit: int = Field(default=MAX_RESULTS_DEFAULT, ge=1, le=MAX_RESULTS_LIMIT)


class SearchGazetteInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    keywords: str = Field(
        ...,
        description="Suchbegriff im BBl-Titel, z.B. 'Berufsbildung', 'Datenschutz', 'Volksinitiative'",
        min_length=2, max_length=200, pattern=KEYWORD_PATTERN,
    )
    language: Language = Field(default=Language.DE)
    year: int | None = Field(default=None, ge=1999, le=2030,
                              description="Optional: Nur dieses Publikationsjahr (z.B. 2024)")
    limit: int = Field(default=MAX_RESULTS_DEFAULT, ge=1, le=MAX_RESULTS_LIMIT)


class GetLawHistoryInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    sr_number: str = Field(
        ...,
        description="SR-Nummer, z.B. '235.1' (DSG), '412.10' (BBG), '101' (BV)",
        min_length=1, max_length=20, pattern=SR_NUMBER_PATTERN,
    )
    language: Language = Field(default=Language.DE)


class SearchTreatiesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    keywords: str | None = Field(
        default=None,
        description="Suchbegriff im Titel, z.B. 'Bildung', 'EU', 'Datenschutz'. Ohne Begriff: neueste Verträge.",
        max_length=200, pattern=KEYWORD_PATTERN,
    )
    language: Language = Field(default=Language.DE)
    limit: int = Field(default=MAX_RESULTS_DEFAULT, ge=1, le=MAX_RESULTS_LIMIT)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool(
    name="fedlex_search_laws",
    description=(
        "Durchsucht die Systematische Rechtssammlung (SR) des Bundes nach Erlasstiteln "
        "und liefert SR-Nummer, Abkürzung, Status und Link.\n"
        "<use_case>Juristische/verwaltungsbezogene Recherche: konsolidiertes Bundesrecht "
        "(Gesetze, Verordnungen, Vereinbarungen) per Stichwort finden.</use_case>\n"
        "<important_notes>Sucht nur im Titel, nicht im Volltext. Standardmässig nur in "
        "Kraft stehende Erlasse (in_force_only=true). Liefert einen strukturierten "
        "Envelope (results + markdown).</important_notes>\n"
        "<example>keywords='Datenschutz', language='de'</example>"
    ),
    annotations={
        "title": "Erlasse der Systematischen Rechtssammlung (SR) suchen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def fedlex_search_laws(params: SearchLawsInput, ctx: Context | None = None) -> FedlexResponse:
    """Durchsucht die Systematische Rechtssammlung (SR) des Bundes nach Erlasstiteln."""
    tool = "fedlex_search_laws"
    lang = params.language.value
    suffix = LANG_SUFFIX[lang]
    kw = params.keywords.lower()
    await _trace(ctx, tool, lang=lang, in_force_only=params.in_force_only)

    in_force_filter = (
        f'\n  ?ca jolux:inForceStatus <{STATUS_IN_FORCE}> .'
        if params.in_force_only else ""
    )

    query = f"""
PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
SELECT DISTINCT ?ca ?title ?titleShort ?srNumber ?inForceStatus WHERE {{
  ?ca a jolux:ConsolidationAbstract ;
      jolux:isRealizedBy ?expr .
  ?expr jolux:title ?title .
  OPTIONAL {{ ?expr jolux:titleShort ?titleShort . }}
  OPTIONAL {{ ?expr jolux:historicalLegalId ?srNumber . }}
  OPTIONAL {{ ?ca jolux:inForceStatus ?inForceStatus . }}
  FILTER(STRENDS(STR(?expr), "{suffix}"))
  FILTER(STRSTARTS(STR(?ca), "https://fedlex.data.admin.ch/eli/cc/"))
  FILTER(CONTAINS(LCASE(STR(?title)), "{sparql_escape(kw)}"))
  {in_force_filter}
}} ORDER BY ?srNumber
LIMIT {params.limit}
"""

    async with _tool_span(tool, lang=lang, in_force_only=params.in_force_only):
        try:
            bindings = await run_sparql(query)

            if not bindings:
                md = (
                    f"Keine Erlasse für **'{params.keywords}'** gefunden "
                    f"[{lang.upper()}, nur gültige: {params.in_force_only}]."
                    + no_match_hint(
                        "**Tipps:** Allgemeineren Begriff verwenden | "
                        "`in_force_only=false` für aufgehobene Erlasse | "
                        "Auf Deutsch suchen (vollständigste Abdeckung)"
                    )
                )
                return _empty(tool, md)

            results: list[dict] = []
            md = result_header(len(bindings), f"SR-Suche '{params.keywords}' [{lang.upper()}]")
            for b in bindings:
                uri = val(b, "ca")
                title = val(b, "title", "(kein Titel)")
                short = val(b, "titleShort")
                sr_num = val(b, "srNumber", "–")
                status_uri = val(b, "inForceStatus")
                st = status_label(status_uri) if status_uri else "–"
                url = fedlex_url(uri, lang)
                results.append({
                    "sr_number": sr_num, "title": title, "title_short": short or None,
                    "status": st, "uri": uri, "url": url,
                })
                short_display = f" ({short})" if short else ""
                md += f"### SR {sr_num}: {title}{short_display}\n"
                md += f"- **Status:** {st}\n"
                md += f"- **Link:** [{url}]({url})\n\n"

            md += FEDLEX_SOURCE
            return _ok(tool, results, md)

        except Exception as e:
            return await _fail(ctx, tool, e)


def _law_detail_markdown(
    b: dict, sr: str, lang: str, successor: dict | None = None,
) -> str:
    """Formatiert die Detailansicht eines Erlasses als Markdown."""
    uri = val(b, "ca")
    title = val(b, "title", "(kein Titel)")
    short = val(b, "titleShort", "–")
    sr_num = val(b, "srNumber", sr)
    status_uri = val(b, "inForceStatus")
    entry_date = val(b, "entryDate", "–")
    url = fedlex_url(uri, lang)
    st = status_label(status_uri) if status_uri else "–"

    out = f"## SR {sr_num}: {title}\n\n"
    out += "| Feld | Wert |\n|---|---|\n"
    out += f"| **Vollständiger Titel** | {title} |\n"
    out += f"| **Abkürzung** | {short} |\n"
    out += f"| **SR-Nummer** | {sr_num} |\n"
    out += f"| **Status** | {st} |\n"
    out += f"| **Inkrafttreten (aktuelle Fassung)** | {entry_date} |\n"
    out += f"| **Sprache** | {lang.upper()} |\n"
    out += f"\n**Direktlink:** [{url}]({url})\n"
    out += f"\n**Daten-URI:** `{uri}`\n"

    if successor:
        s_uri = val(successor, "ca")
        s_title = val(successor, "title", "(kein Titel)")
        s_short = val(successor, "titleShort", "–")
        s_sr = val(successor, "srNumber", "–")
        s_entry = val(successor, "entryDate", "–")
        s_url = fedlex_url(s_uri, lang)
        out += "\n---\n### ⚠️ Nachfolge-Erlass (in Kraft)\n\n"
        out += "| Feld | Wert |\n|---|---|\n"
        out += f"| **Vollständiger Titel** | {s_title} |\n"
        out += f"| **Abkürzung** | {s_short} |\n"
        if s_sr != "–":
            out += f"| **SR-Nummer** | {s_sr} |\n"
        out += f"| **Inkrafttreten** | {s_entry} |\n"
        out += "| **Status** | ✅ In Kraft |\n"
        out += f"\n**Direktlink:** [{s_url}]({s_url})\n"

    out += FEDLEX_SOURCE
    return out


def _law_record(b: dict, lang: str) -> dict:
    uri = val(b, "ca")
    return {
        "sr_number": val(b, "srNumber") or None,
        "title": val(b, "title", "(kein Titel)"),
        "title_short": val(b, "titleShort") or None,
        "status": status_label(val(b, "inForceStatus")) if val(b, "inForceStatus") else None,
        "entry_date": val(b, "entryDate") or None,
        "uri": uri,
        "url": fedlex_url(uri, lang),
    }


@mcp.tool(
    name="fedlex_get_law_by_sr",
    description=(
        "Ruft einen Bundeserlass anhand seiner SR-Nummer ab (Detailansicht mit "
        "Titel, Abkürzung, Status, Inkrafttreten, Link).\n"
        "<use_case>Wenn die SR-Nummer bekannt ist (z.B. aus fedlex_search_laws) und "
        "vollständige Metadaten zu einem Erlass gebraucht werden.</use_case>\n"
        "<important_notes>Bei aufgehobenen Erlassen wird — sofern auffindbar — der "
        "Nachfolge-Erlass mitgeliefert. SR-Nummer mit Punkt trennen (235.1).</important_notes>\n"
        "<example>sr_number='235.1'</example>"
    ),
    annotations={
        "title": "Erlass nach SR-Nummer abrufen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def fedlex_get_law_by_sr(params: GetLawBySrInput, ctx: Context | None = None) -> FedlexResponse:
    """Ruft einen Bundeserlass anhand seiner SR-Nummer ab (Detailansicht)."""
    tool = "fedlex_get_law_by_sr"
    lang = params.language.value
    suffix = LANG_SUFFIX[lang]
    sr = params.sr_number.strip()
    await _trace(ctx, tool, lang=lang, sr_number=sr)

    query = f"""
PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
SELECT DISTINCT ?ca ?title ?titleShort ?srNumber ?inForceStatus ?entryDate WHERE {{
  ?ca a jolux:ConsolidationAbstract ;
      jolux:isRealizedBy ?expr .
  ?expr jolux:title ?title ;
        jolux:historicalLegalId ?srNumber .
  OPTIONAL {{ ?expr jolux:titleShort ?titleShort . }}
  OPTIONAL {{ ?ca jolux:inForceStatus ?inForceStatus . }}
  OPTIONAL {{ ?ca jolux:dateEntryInForce ?entryDate . }}
  FILTER(STRENDS(STR(?expr), "{suffix}"))
  FILTER(STR(?srNumber) = "{sparql_escape(sr)}")
}} ORDER BY DESC(?entryDate)
LIMIT 10
"""

    async with _tool_span(tool, lang=lang, sr_number=sr):
        try:
            bindings = await run_sparql(query)

            if not bindings:
                md = (
                    f"Kein Erlass mit SR-Nummer **{sr}** gefunden [{lang.upper()}]."
                    + no_match_hint(
                        "**Mögliche Ursachen:**\n"
                        "- SR-Nummer falsch (Punkt als Trennzeichen: '235.1', nicht '235,1')\n"
                        "- Erlass in dieser Sprache nicht vorhanden\n"
                        "- Erlass aufgehoben (mit `in_force_only=false` in `fedlex_search_laws` suchen)"
                    )
                )
                return _empty(tool, md)

            # Bevorzuge den gültigen Erlass (In Kraft) gegenüber aufgehobenen Fassungen,
            # da mehrere ConsolidationAbstract-Einträge dieselbe SR-Nummer teilen können
            # (z.B. altes DSG von 1992 und revidiertes nDSG von 2020 unter SR 235.1).
            in_force = [b for b in bindings if val(b, "inForceStatus") == STATUS_IN_FORCE]
            b = in_force[0] if in_force else bindings[0]
            status_uri = val(b, "inForceStatus")

            # Wenn der Erlass nicht mehr in Kraft ist, Nachfolge-Erlass suchen.
            successor = None
            if status_uri == STATUS_NO_LONGER_FORCE:
                short_name = val(b, "titleShort")
                if short_name:
                    succ_query = f"""
PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
SELECT DISTINCT ?ca ?title ?titleShort ?srNumber ?inForceStatus ?entryDate WHERE {{
  ?ca a jolux:ConsolidationAbstract ;
      jolux:isRealizedBy ?expr ;
      jolux:inForceStatus <{STATUS_IN_FORCE}> .
  ?expr jolux:title ?title ;
        jolux:titleShort ?titleShort .
  OPTIONAL {{ ?expr jolux:historicalLegalId ?srNumber . }}
  OPTIONAL {{ ?ca jolux:dateEntryInForce ?entryDate . }}
  FILTER(STRENDS(STR(?expr), "{suffix}"))
  FILTER(STRSTARTS(STR(?ca), "https://fedlex.data.admin.ch/eli/cc/"))
  FILTER(STR(?titleShort) = "{sparql_escape(short_name)}")
}} LIMIT 1
"""
                    succ_bindings = await run_sparql(succ_query)
                    if succ_bindings:
                        successor = succ_bindings[0]

            record = _law_record(b, lang)
            if successor:
                record["successor"] = _law_record(successor, lang)
            md = _law_detail_markdown(b, sr, lang, successor)
            return _ok(tool, [record], md)

        except Exception as e:
            return await _fail(ctx, tool, e)


@mcp.tool(
    name="fedlex_get_recent_publications",
    description=(
        "Ruft die neuesten Publikationen der Amtlichen Sammlung (AS) ab.\n"
        "<use_case>Regelmässiges Monitoring von Rechtsänderungen — was wurde in den "
        "letzten N Tagen neu publiziert oder geändert?</use_case>\n"
        "<important_notes>Liefert Erstpublikationen (AS), nicht den konsolidierten "
        "Stand. Zeitfenster über `days` (1–365).</important_notes>\n"
        "<example>days=30, language='de'</example>"
    ),
    annotations={
        "title": "Neueste Bundesrechtspublikationen (AS) abrufen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def fedlex_get_recent_publications(
    params: GetRecentPublicationsInput, ctx: Context | None = None
) -> FedlexResponse:
    """Ruft die neuesten Publikationen der Amtlichen Sammlung (AS) ab."""
    tool = "fedlex_get_recent_publications"
    lang = params.language.value
    suffix = LANG_SUFFIX[lang]
    since_date = (date.today() - timedelta(days=params.days)).isoformat()
    await _trace(ctx, tool, lang=lang, days=params.days)

    query = f"""
PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT DISTINCT ?act ?title ?pubDate WHERE {{
  ?act a jolux:Act ;
       jolux:isRealizedBy ?expr ;
       jolux:publicationDate ?pubDate .
  ?expr jolux:title ?title .
  FILTER(STRENDS(STR(?expr), "{suffix}"))
  FILTER(xsd:date(?pubDate) >= "{since_date}"^^xsd:date)
}} ORDER BY DESC(?pubDate)
LIMIT {params.limit}
"""

    async with _tool_span(tool, lang=lang, days=params.days):
        try:
            bindings = await run_sparql(query)

            if not bindings:
                md = (
                    f"Keine Publikationen in den letzten {params.days} Tagen gefunden [{lang.upper()}]."
                    + no_match_hint("**Tipp:** `days` erhöhen, z.B. `days=90`.")
                )
                return _empty(tool, md)

            results: list[dict] = []
            md = result_header(len(bindings), f"AS-Publikationen seit {since_date} [{lang.upper()}]")
            for b in bindings:
                uri = val(b, "act")
                title = val(b, "title", "(kein Titel)")
                pub_date = val(b, "pubDate", "–")
                url = fedlex_url(uri, lang)
                results.append({"title": title, "publication_date": pub_date, "uri": uri, "url": url})
                md += f"### {pub_date}\n**{title}**\n[{url}]({url})\n\n"

            md += FEDLEX_SOURCE
            return _ok(tool, results, md)

        except Exception as e:
            return await _fail(ctx, tool, e)


@mcp.tool(
    name="fedlex_get_upcoming_changes",
    description=(
        "Ruft Erlasse ab, die in den nächsten N Tagen in Kraft treten.\n"
        "<use_case>Proaktives Rechtsmonitoring für Verwaltung und Schulen: welche "
        "Gesetze werden bald wirksam (Datenschutz, Bildung, Regulierung)?</use_case>\n"
        "<important_notes>Berücksichtigt nur künftige Inkraftsetzungen (dateEntryInForce "
        "> heute). Fenster über `days_ahead` (1–365).</important_notes>\n"
        "<example>days_ahead=90</example>"
    ),
    annotations={
        "title": "Bevorstehende Rechtsänderungen abrufen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def fedlex_get_upcoming_changes(
    params: GetUpcomingChangesInput, ctx: Context | None = None
) -> FedlexResponse:
    """Ruft Erlasse ab, die in den nächsten N Tagen in Kraft treten."""
    tool = "fedlex_get_upcoming_changes"
    lang = params.language.value
    suffix = LANG_SUFFIX[lang]
    today = date.today().isoformat()
    future = (date.today() + timedelta(days=params.days_ahead)).isoformat()
    await _trace(ctx, tool, lang=lang, days_ahead=params.days_ahead)

    query = f"""
PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT DISTINCT ?ca ?title ?titleShort ?srNumber ?entryDate WHERE {{
  ?ca a jolux:ConsolidationAbstract ;
      jolux:isRealizedBy ?expr ;
      jolux:dateEntryInForce ?entryDate .
  ?expr jolux:title ?title .
  OPTIONAL {{ ?expr jolux:titleShort ?titleShort . }}
  OPTIONAL {{ ?expr jolux:historicalLegalId ?srNumber . }}
  FILTER(STRENDS(STR(?expr), "{suffix}"))
  FILTER(STRSTARTS(STR(?ca), "https://fedlex.data.admin.ch/eli/cc/"))
  FILTER(xsd:date(?entryDate) > "{today}"^^xsd:date)
  FILTER(xsd:date(?entryDate) <= "{future}"^^xsd:date)
}} ORDER BY ASC(?entryDate)
LIMIT {params.limit}
"""

    async with _tool_span(tool, lang=lang, days_ahead=params.days_ahead):
        try:
            bindings = await run_sparql(query)

            if not bindings:
                md = (
                    f"Keine bevorstehenden Rechtsänderungen in den nächsten "
                    f"{params.days_ahead} Tagen [{lang.upper()}]."
                    + no_match_hint("**Tipp:** `days_ahead` erhöhen, z.B. `days_ahead=180`.")
                )
                return _empty(tool, md)

            results: list[dict] = []
            md = result_header(
                len(bindings), f"Bevorstehende Änderungen bis {future} [{lang.upper()}]"
            )
            for b in bindings:
                uri = val(b, "ca")
                title = val(b, "title", "(kein Titel)")
                short = val(b, "titleShort")
                sr_num = val(b, "srNumber", "–")
                entry = val(b, "entryDate", "–")
                url = fedlex_url(uri, lang)
                results.append({
                    "sr_number": sr_num if sr_num != "–" else None,
                    "title": title, "title_short": short or None,
                    "entry_date": entry, "uri": uri, "url": url,
                })
                short_display = f" ({short})" if short else ""
                sr_display = f"SR {sr_num}" if sr_num != "–" else "SR –"
                md += f"### 📅 {entry} — {sr_display}: {title}{short_display}\n"
                md += f"[{url}]({url})\n\n"

            md += FEDLEX_SOURCE
            return _ok(tool, results, md)

        except Exception as e:
            return await _fail(ctx, tool, e)


@mcp.tool(
    name="fedlex_search_gazette",
    description=(
        "Durchsucht das Bundesblatt (BBl) nach amtlichen Publikationen.\n"
        "<use_case>Politisches Frühwarnsystem: Botschaften des Bundesrates, "
        "Parlaments- und Volksinitiativen, Vernehmlassungen.</use_case>\n"
        "<important_notes>BBl ≠ konsolidiertes Recht — für geltende Gesetze "
        "`fedlex_search_laws` nutzen. Optional auf ein Jahr einschränken.</important_notes>\n"
        "<example>keywords='Berufsbildung', year=2024</example>"
    ),
    annotations={
        "title": "Im Bundesblatt (BBl) suchen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def fedlex_search_gazette(params: SearchGazetteInput, ctx: Context | None = None) -> FedlexResponse:
    """Durchsucht das Bundesblatt (BBl) nach amtlichen Publikationen."""
    tool = "fedlex_search_gazette"
    lang = params.language.value
    suffix = LANG_SUFFIX[lang]
    kw = params.keywords.lower()
    await _trace(ctx, tool, lang=lang, year=params.year)

    year_filter = (
        f'FILTER(STRSTARTS(STR(?pubDate), "{params.year}"))'
        if params.year else ""
    )

    query = f"""
PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
SELECT DISTINCT ?act ?title ?pubDate WHERE {{
  ?act a jolux:Act ;
       jolux:isRealizedBy ?expr ;
       jolux:publicationDate ?pubDate .
  ?expr jolux:title ?title .
  FILTER(STRENDS(STR(?expr), "{suffix}"))
  FILTER(STRSTARTS(STR(?act), "https://fedlex.data.admin.ch/eli/fga/"))
  FILTER(CONTAINS(LCASE(STR(?title)), "{sparql_escape(kw)}"))
  {year_filter}
}} ORDER BY DESC(?pubDate)
LIMIT {params.limit}
"""

    async with _tool_span(tool, lang=lang, year=params.year):
        try:
            bindings = await run_sparql(query)

            yr_txt = f" ({params.year})" if params.year else ""
            if not bindings:
                md = (
                    f"Keine BBl-Publikation für **'{params.keywords}'**{yr_txt} [{lang.upper()}]."
                    + no_match_hint(
                        "**Tipps:** Allgemeineren Begriff verwenden | "
                        "Jahr weglassen | `fedlex_search_laws` für konsolidiertes Recht"
                    )
                )
                return _empty(tool, md)

            results: list[dict] = []
            md = result_header(
                len(bindings), f"BBl-Suche '{params.keywords}'{yr_txt} [{lang.upper()}]"
            )
            for b in bindings:
                uri = val(b, "act")
                title = val(b, "title", "(kein Titel)")
                pub_date = val(b, "pubDate", "–")
                url = fedlex_url(uri, lang)
                results.append({"title": title, "publication_date": pub_date, "uri": uri, "url": url})
                md += f"### {pub_date}\n**{title}**\n[{url}]({url})\n\n"

            md += FEDLEX_SOURCE
            return _ok(tool, results, md)

        except Exception as e:
            return await _fail(ctx, tool, e)


@mcp.tool(
    name="fedlex_get_law_history",
    description=(
        "Ruft die Versionsgeschichte (alle konsolidierten Fassungen) eines Erlasses ab.\n"
        "<use_case>Nachvollziehen, wann welche Fassung galt — z.B. alte vs. revidierte "
        "Gesetzesfassung (DSG 235.1: 1992 vs. nDSG 2020).</use_case>\n"
        "<important_notes>Sortiert nach Inkrafttreten absteigend, max. 50 Fassungen. "
        "SR-Nummer mit Punkt trennen.</important_notes>\n"
        "<example>sr_number='235.1'</example>"
    ),
    annotations={
        "title": "Versionsgeschichte eines Erlasses abrufen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def fedlex_get_law_history(params: GetLawHistoryInput, ctx: Context | None = None) -> FedlexResponse:
    """Ruft die Versionsgeschichte (alle konsolidierten Fassungen) eines Erlasses ab."""
    tool = "fedlex_get_law_history"
    lang = params.language.value
    suffix = LANG_SUFFIX[lang]
    sr = params.sr_number.strip()
    await _trace(ctx, tool, lang=lang, sr_number=sr)

    query = f"""
PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
SELECT DISTINCT ?ca ?title ?srNumber ?entryDate ?inForceStatus WHERE {{
  ?ca a jolux:ConsolidationAbstract ;
      jolux:isRealizedBy ?expr .
  ?expr jolux:title ?title ;
        jolux:historicalLegalId ?srNumber .
  OPTIONAL {{ ?ca jolux:dateEntryInForce ?entryDate . }}
  OPTIONAL {{ ?ca jolux:inForceStatus ?inForceStatus . }}
  FILTER(STRENDS(STR(?expr), "{suffix}"))
  FILTER(STR(?srNumber) = "{sparql_escape(sr)}")
}} ORDER BY DESC(?entryDate)
LIMIT 50
"""

    async with _tool_span(tool, lang=lang, sr_number=sr):
        try:
            bindings = await run_sparql(query)

            if not bindings:
                md = (
                    f"Keine Versionsgeschichte für SR-Nummer **{sr}** [{lang.upper()}]."
                    + no_match_hint("**Tipp:** SR-Nummer mit `fedlex_get_law_by_sr` überprüfen.")
                )
                return _empty(tool, md)

            title_sample = val(bindings[0], "title", sr)
            results: list[dict] = []
            md = f"## Versionsgeschichte: {title_sample}\n"
            md += f"**SR {sr}** | {lang.upper()}\n\n"
            md += "| Fassung | Inkrafttreten | Status | Link |\n"
            md += "|---|---|---|---|\n"

            total = len(bindings)
            for i, b in enumerate(bindings):
                uri = val(b, "ca")
                entry = val(b, "entryDate", "–")
                status_uri = val(b, "inForceStatus")
                url = fedlex_url(uri, lang)
                st = status_label(status_uri) if status_uri else "–"
                version = total - i
                results.append({
                    "version": version, "entry_date": entry, "status": st,
                    "uri": uri, "url": url,
                })
                md += f"| v{version} | {entry} | {st} | [→]({url}) |\n"

            md += FEDLEX_SOURCE
            return _ok(tool, results, md)

        except Exception as e:
            return await _fail(ctx, tool, e)


@mcp.tool(
    name="fedlex_search_treaties",
    description=(
        "Sucht internationale Staatsverträge der Schweiz (SR-Nummern beginnen mit '0.').\n"
        "<use_case>Recherche zu bi-/multilateralen Abkommen: EU-Bilaterale, "
        "Doppelbesteuerung, Europarats-Konventionen (Datenschutz, Menschenrechte).</use_case>\n"
        "<important_notes>Ohne Suchbegriff werden die neuesten Verträge gelistet. "
        "Sucht nur im Titel.</important_notes>\n"
        "<example>keywords='Datenschutz'</example>"
    ),
    annotations={
        "title": "Staatsverträge der Schweiz suchen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def fedlex_search_treaties(params: SearchTreatiesInput, ctx: Context | None = None) -> FedlexResponse:
    """Sucht internationale Staatsverträge der Schweiz (SR-Nummern beginnen mit '0.')."""
    tool = "fedlex_search_treaties"
    lang = params.language.value
    suffix = LANG_SUFFIX[lang]
    await _trace(ctx, tool, lang=lang, has_keywords=bool(params.keywords))

    kw_filter = (
        f'FILTER(CONTAINS(LCASE(STR(?title)), "{sparql_escape(params.keywords.lower())}"))'
        if params.keywords else ""
    )

    query = f"""
PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
SELECT DISTINCT ?ca ?title ?srNumber ?entryDate WHERE {{
  ?ca a jolux:ConsolidationAbstract ;
      jolux:isRealizedBy ?expr .
  ?expr jolux:title ?title ;
        jolux:historicalLegalId ?srNumber .
  OPTIONAL {{ ?ca jolux:dateEntryInForce ?entryDate . }}
  FILTER(STRENDS(STR(?expr), "{suffix}"))
  FILTER(STRSTARTS(STR(?srNumber), "0."))
  {kw_filter}
}} ORDER BY ?srNumber
LIMIT {params.limit}
"""

    async with _tool_span(tool, lang=lang, has_keywords=bool(params.keywords)):
        try:
            bindings = await run_sparql(query)

            kw_txt = f"'{params.keywords}'" if params.keywords else "alle"
            if not bindings:
                md = (
                    f"Keine Staatsverträge für {kw_txt} [{lang.upper()}]."
                    + no_match_hint("**Tipp:** Suchbegriff anpassen oder weglassen.")
                )
                return _empty(tool, md)

            results: list[dict] = []
            md = result_header(len(bindings), f"Staatsverträge {kw_txt} [{lang.upper()}]")
            for b in bindings:
                uri = val(b, "ca")
                title = val(b, "title", "(kein Titel)")
                sr_num = val(b, "srNumber", "–")
                entry = val(b, "entryDate", "–")
                url = fedlex_url(uri, lang)
                results.append({
                    "sr_number": sr_num, "title": title, "entry_date": entry,
                    "uri": uri, "url": url,
                })
                md += f"### SR {sr_num}: {title}\n"
                md += f"- **Inkrafttreten:** {entry}\n"
                md += f"- **Link:** [{url}]({url})\n\n"

            md += FEDLEX_SOURCE
            return _ok(tool, results, md)

        except Exception as e:
            return await _fail(ctx, tool, e)


# ===========================================================================
# Erweiterung v1.1.0 — Vernehmlassungen (Fedlex) & TERMDAT (LINDAS)
# ===========================================================================
# Beide Quellen sind SPARQL-basiert; die Fedlex-Infrastruktur oben (Envelope,
# Escaping, Egress-Allow-List, Fehler-Masking, Retry) wird wiederverwendet.
# Neu ist nur der zweite, ISOLIERTE Endpoint LINDAS für TERMDAT.


class TermLanguage(StrEnum):
    """Sprachen von TERMDAT. Zusätzlich zu den vier Landessprachen auch EN.

    Achtung: `rm` (Rätoromanisch) ist im LINDAS-Teilbestand faktisch nicht
    besetzt (0 Namen live verifiziert) — als Zielsprache erlaubt, liefert aber
    in aller Regel keinen Treffer.
    """

    DE = "de"
    FR = "fr"
    IT = "it"
    RM = "rm"
    EN = "en"


# ---------------------------------------------------------------------------
# Helfer — Vernehmlassungen
# ---------------------------------------------------------------------------
# Die eigentliche Logik (zentrale Fristenberechnung, abgeleiteter Status,
# typisiertes Modell, Query-Bausteine, Themenfilter) liegt im isolierten
# consultations-Modul — getrennt von der SR-/AS-/BBl-Schicht. Hier nur
# rückwärtskompatible Re-Exports und der Markdown-Renderer.
consultation_status_label = consultations.CONSULTATION_STATUS_LABELS.get
consultation_event_url = consultations.event_url


def _consultation_line(r: consultations.Consultation, *, with_days: bool = True) -> str:
    """Markdown-Zeilen für einen Vernehmlassungs-Datensatz (Liste)."""
    flag = " ⚠️ status_conflict" if r.status_conflict else ""
    deadline = r.deadline.isoformat() if r.deadline else "keine Frist"
    if with_days and r.days_remaining is not None:
        days = "heute" if r.days_remaining == 0 else (
            f"in {r.days_remaining} Tagen" if r.days_remaining > 0
            else f"vor {abs(r.days_remaining)} Tagen abgelaufen"
        )
        head = f"### 📅 Frist {deadline} ({days}) — {r.title}{flag}\n"
    else:
        head = f"### {r.title}{flag}\n"
    md = head
    md += f"- **Status:** {r.status}"
    if r.days_remaining is not None:
        md += f" | **days_remaining:** {r.days_remaining}"
    md += "\n"
    md += f"- **Frist:** {deadline}"
    if r.opened_on:
        md += f" | **Eröffnet:** {r.opened_on.isoformat()}"
    md += "\n"
    fed = r.lead_department or "–"
    md += f"- **Federführung:** {fed}"
    md += f" / {r.lead_office}\n" if r.lead_office else "\n"
    if r.event_id:
        md += f"- **eventId:** `{r.event_id}`\n"
    if r.source_url:
        md += f"- **Link:** [{r.source_url}]({r.source_url})\n"
    md += "\n"
    return md


# ---------------------------------------------------------------------------
# Helfer — TERMDAT
# ---------------------------------------------------------------------------


def termdat_concept_id(value: str) -> str | None:
    """Normalisiert eine TERMDAT-Eingabe auf die numerische Konzept-ID.

    Akzeptiert (Quirk 3): reine ID (`40109`), Konzept-URI
    (`…/termdat/40109`), Term-URI mit Sprach-/Positionssuffix
    (`…/termdat/40109/3/de`) sowie die `…/entry/40109`-Form. Da nur Ziffern
    extrahiert und die URI serverseitig konstruiert wird, ist die Eingabe
    injektionssicher, unabhängig vom restlichen Text.
    """
    s = value.strip()
    if s.isdigit():
        return s
    m = re.search(r"/termdat/(\d+)", s) or re.search(r"/entry/(\d+)", s)
    return m.group(1) if m else None


def termdat_concept_uri(concept_id: str) -> str:
    return f"{TERMDAT_REGISTER_BASE}/{concept_id}"


def termdat_entry_url(concept_id: str) -> str:
    """Menschenlesbarer Link auf den TERMDAT-Eintrag (Web-Frontend)."""
    return f"https://www.termdat.bk.admin.ch/entry/{concept_id}"


def _termdat_ok(tool: str, results: list[dict], markdown: str,
                match_type: Literal["exact", "none"] = "exact",
                message: str | None = None) -> FedlexResponse:
    """Envelope für TERMDAT — trägt IMMER die TERMDAT-Attribution (Teilbestand)."""
    return _ok(tool, results, markdown + TERMDAT_SOURCE, match_type=match_type,
               source=ATTRIBUTION_TERMDAT, license=TERMDAT_LICENSE, message=message)


def _termdat_empty(tool: str, markdown: str, message: str | None = None) -> FedlexResponse:
    return _empty(tool, markdown + TERMDAT_SOURCE, source=ATTRIBUTION_TERMDAT,
                  license=TERMDAT_LICENSE, message=message)


# ---------------------------------------------------------------------------
# Input-Modelle — neue Tools
# ---------------------------------------------------------------------------


class GetOpenConsultationsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    keyword: str | None = Field(
        default=None,
        description="Optionaler exakter Titel-Teilstring, z.B. 'Datenschutz'. Achtung: eng — "
                    "'Volksschule' findet 0 Treffer. Für Bildungsthemen `topic='education'` nutzen.",
        min_length=2, max_length=200, pattern=KEYWORD_PATTERN,
    )
    topic: Literal["education"] | None = Field(
        default=None,
        description="Themen-Stichwort-Union (Freitext, keine Taxonomie). 'education' deckt "
                    "Bildung/Schule/Berufsbildung/Hochschule/… ab; die gesuchten Begriffe "
                    "werden in der Antwort ausgewiesen.",
    )
    language: Language = Field(default=Language.DE, description="Sprache des Titels: de, fr, it, rm")
    limit: int = Field(default=MAX_RESULTS_DEFAULT, ge=1, le=MAX_RESULTS_LIMIT,
                       description=f"Maximale Trefferzahl (1–{MAX_RESULTS_LIMIT})")


class SearchConsultationsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    keyword: str | None = Field(
        default=None,
        description="Suchbegriff in Titel und Beschreibung. Ohne Begriff: neueste Vernehmlassungen.",
        min_length=2, max_length=200, pattern=KEYWORD_PATTERN,
    )
    topic: Literal["education"] | None = Field(
        default=None,
        description="Themen-Stichwort-Union (Freitext im Titel). Die gesuchten Begriffe werden "
                    "in der Antwort ausgewiesen.",
    )
    status: Literal[
        "in_preparation", "planned", "running",
        "closed_awaiting_opinions", "closed_awaiting_report", "closed", "withdrawn",
    ] | None = Field(default=None, description="Optionaler Status-Filter (Kurzcode).")
    from_date: date | None = Field(default=None, description="Frist frühestens (eventEndDate >=).")
    to_date: date | None = Field(default=None, description="Frist spätestens (eventEndDate <=).")
    institution: str | None = Field(
        default=None, description="Teilstring im federführenden Departement/Amt (deutsches Label).",
        min_length=2, max_length=100, pattern=KEYWORD_PATTERN,
    )
    language: Language = Field(default=Language.DE)
    limit: int = Field(default=MAX_RESULTS_DEFAULT, ge=1, le=MAX_RESULTS_LIMIT)


class GetConsultationInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    event_id: str = Field(
        ...,
        description="eventId der Vernehmlassung, z.B. 'proj/2026/71/cons_1'.",
        min_length=8, max_length=60, pattern=EVENT_ID_PATTERN,
    )
    language: Language = Field(default=Language.DE)


class TermdatLookupInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    term: str = Field(
        ...,
        description="Fachbegriff, z.B. 'Volksschule', 'Datenschutz'.",
        min_length=2, max_length=200, pattern=KEYWORD_PATTERN,
    )
    target_languages: list[TermLanguage] = Field(
        default_factory=lambda: [TermLanguage.DE, TermLanguage.FR, TermLanguage.IT,
                                 TermLanguage.RM, TermLanguage.EN],
        description="Zielsprachen der Entsprechungen (de, fr, it, rm, en). Standard: alle.",
        max_length=5,
    )
    limit: int = Field(default=MAX_RESULTS_DEFAULT, ge=1, le=MAX_RESULTS_LIMIT,
                       description="Maximale Zahl unterschiedlicher Konzepte.")


class TermdatGetConceptInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    concept: str = Field(
        ...,
        description=(
            "TERMDAT-ID oder -URI. Akzeptiert '40109', "
            "'https://register.ld.admin.ch/termdat/40109' oder eine Term-URI "
            "wie '…/termdat/40109/3/de'."
        ),
        min_length=1, max_length=120, pattern=TERMDAT_INPUT_PATTERN,
    )


# ---------------------------------------------------------------------------
# Tools — Vernehmlassungen
# ---------------------------------------------------------------------------


@mcp.tool(
    name="fedlex_get_open_consultations",
    description=(
        "Listet aktuell OFFENE Vernehmlassungen des Bundes (Fristen-Monitoring).\n"
        "<use_case>«Auf welche Vorlagen kann man jetzt noch Stellung nehmen, und bis "
        "wann?» — vorparlamentarisches Verfahren, Frist-Überwachung.</use_case>\n"
        "<important_notes>Filtert über die Frist (eventEndDate >= heute in Europe/Zurich, "
        "Fristtag inklusive), NICHT über den Status — die Frist ist massgebend. Jeder "
        "Treffer führt deadline, days_remaining (zur Laufzeit berechnet, 0 = Frist heute) "
        "und einen abgeleiteten status; bei Widerspruch zum Quell-Status status_conflict=true. "
        "Sortiert nach kürzester Restfrist. Thema via topic='education' (ausgewiesene "
        "Stichwort-Union) oder exaktem keyword. Leeres Resultat = «nichts offen», NICHT "
        "«nichts kommt».</important_notes>\n"
        "<example>topic='education'</example>"
    ),
    annotations={
        "title": "Offene Vernehmlassungen (Fristen-Monitoring)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def fedlex_get_open_consultations(
    params: GetOpenConsultationsInput, ctx: Context | None = None
) -> FedlexResponse:
    """Listet aktuell offene Vernehmlassungen, gefiltert über die Frist."""
    tool = "fedlex_get_open_consultations"
    lang = params.language.value
    # Zentrale Europe/Zurich-Uhr, zur Laufzeit — nie gecacht, nie geschätzt.
    today = today_in_zurich()
    retrieved_at = consultations.now_iso()
    terms = consultations.effective_terms(params.topic, params.keyword)
    filter_note = consultations.describe_filter(params.topic, terms)
    await _trace(ctx, tool, lang=lang, topic=params.topic, has_keyword=bool(params.keyword))

    query = consultations.build_open_query(lang, terms, today, params.limit)
    thema = f" zum Thema «{params.topic or params.keyword}»" if terms else ""

    async with _tool_span(tool, lang=lang, topic=params.topic):
        try:
            bindings = await run_sparql(query)

            if not bindings:
                # Leeres Resultat ist eine Sachaussage, kein Fehler (ARCH-003):
                # «nichts offen» heisst NICHT «nichts kommt».
                msg = (
                    f"Aktuell keine offenen Vernehmlassungen{thema}; "
                    f"geprüft {retrieved_at} (heute {today.isoformat()}, Europe/Zurich)."
                )
                md = f"## Vernehmlassungen — offen{thema} [{lang.upper()}]\n\n{msg}\n"
                if filter_note:
                    md += f"\n_{filter_note}_\n"
                md += no_match_hint(
                    "**Tipps:** ohne Filter erneut versuchen | mit "
                    "`fedlex_search_consultations` auch abgeschlossene Verfahren durchsuchen. "
                    "«Keine offenen» heisst nicht «keine geplant» — MCP ist Pull-basiert, "
                    "der Server pusht keine Benachrichtigungen."
                )
                return _empty(tool, md, source=ATTRIBUTION_FEDLEX, message=msg)

            records = consultations.records_from_bindings(bindings, lang, today, retrieved_at)
            results = [r.model_dump(mode="json") for r in records]
            conflicts = sum(1 for r in records if r.status_conflict)
            md = result_header(len(records), f"Offene Vernehmlassungen{thema} [{lang.upper()}]")
            md += (
                f"_Frist-basiert (eventEndDate >= {today.isoformat()}, Europe/Zurich, "
                f"Fristtag inklusive); sortiert nach kürzester Restfrist; "
                f"retrieved_at {retrieved_at}._\n\n"
            )
            if filter_note:
                md += f"_{filter_note}_\n\n"
            for r in records:
                md += _consultation_line(r)
            if conflicts:
                md += (
                    f"> ⚠️ {conflicts} Eintrag/Einträge mit Status-Frist-Konflikt "
                    "(Quell-Status widerspricht der Frist — die Frist ist massgebend).\n\n"
                )
            md += f"\n---\n*{ATTRIBUTION_FEDLEX}*"
            return _ok(tool, results, md, source=ATTRIBUTION_FEDLEX, message=filter_note)

        except Exception as e:
            return await _fail(ctx, tool, e, source=ATTRIBUTION_FEDLEX)


@mcp.tool(
    name="fedlex_search_consultations",
    description=(
        "Volltextsuche über Vernehmlassungen (Titel und Beschreibung), mit Filtern.\n"
        "<use_case>Recherche im vorparlamentarischen Verfahren — auch abgeschlossene "
        "Vernehmlassungen, nach Status, Zeitraum oder federführendem Amt.</use_case>\n"
        "<important_notes>Filter: topic (Stichwort-Union, ausgewiesen), keyword (Titel+"
        "Beschreibung), status (Kurzcode), from_date/to_date auf die Frist, institution "
        "(Teilstring im Amt). status ist abgeleitet (Frist gewinnt), days_remaining zur "
        "Laufzeit. Für reines Fristen-Monitoring offener Verfahren "
        "`fedlex_get_open_consultations` nutzen.</important_notes>\n"
        "<example>topic='education', status='closed'</example>"
    ),
    annotations={
        "title": "Vernehmlassungen durchsuchen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def fedlex_search_consultations(
    params: SearchConsultationsInput, ctx: Context | None = None
) -> FedlexResponse:
    """Volltextsuche über Titel/Beschreibung von Vernehmlassungen, mit Filtern."""
    tool = "fedlex_search_consultations"
    lang = params.language.value
    today = today_in_zurich()
    retrieved_at = consultations.now_iso()
    terms = consultations.effective_terms(params.topic, None)
    filter_note = consultations.describe_filter(params.topic, terms)
    status_uri = CONSULTATION_STATUS_ALIASES[params.status] if params.status else None
    await _trace(ctx, tool, lang=lang, topic=params.topic, has_keyword=bool(params.keyword),
                 status=params.status)

    query = consultations.build_search_query(
        lang, terms, params.keyword, status_uri,
        params.from_date, params.to_date, params.institution, params.limit,
    )

    async with _tool_span(tool, lang=lang, status=params.status):
        try:
            bindings = await run_sparql(query)

            kw_txt = f"'{params.topic or params.keyword}'" if (params.topic or params.keyword) else "alle"
            if not bindings:
                md = (
                    f"Keine Vernehmlassungen für {kw_txt} mit den gewählten Filtern [{lang.upper()}]."
                    + no_match_hint(
                        "**Tipps:** Filter lockern (status/institution/Zeitraum weglassen) | "
                        "allgemeineren Begriff verwenden."
                    )
                )
                return _empty(tool, md, source=ATTRIBUTION_FEDLEX)

            records = consultations.records_from_bindings(bindings, lang, today, retrieved_at)
            results = [r.model_dump(mode="json") for r in records]
            md = result_header(len(records), f"Vernehmlassungen {kw_txt} [{lang.upper()}]")
            md += f"_Status abgeleitet (Frist gewinnt); retrieved_at {retrieved_at}._\n\n"
            if filter_note:
                md += f"_{filter_note}_\n\n"
            for r in records:
                md += _consultation_line(r, with_days=False)
            md += f"\n---\n*{ATTRIBUTION_FEDLEX}*"
            return _ok(tool, results, md, source=ATTRIBUTION_FEDLEX, message=filter_note)

        except Exception as e:
            return await _fail(ctx, tool, e, source=ATTRIBUTION_FEDLEX)


@mcp.tool(
    name="fedlex_get_consultation",
    description=(
        "Detail zu einer Vernehmlassung anhand ihrer eventId.\n"
        "<use_case>Vollbild zu einem Verfahren: Fristen, federführendes Amt, Status, "
        "Vernehmlassungsunterlagen und verknüpfte Rechtsressource — Grundlage für eine "
        "Stellungnahme.</use_case>\n"
        "<important_notes>Führt deadline, days_remaining (zur Laufzeit, Europe/Zurich) und "
        "einen abgeleiteten status (Frist gewinnt). Ohne hasSubTask: deadline=null mit "
        "Hinweis (wirft nicht). status_conflict markiert einen Widerspruch zwischen Quell-"
        "Status und Frist. eventId z.B. aus fedlex_get_open_consultations.</important_notes>\n"
        "<example>event_id='proj/2026/71/cons_1'</example>"
    ),
    annotations={
        "title": "Vernehmlassung im Detail abrufen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def fedlex_get_consultation(
    params: GetConsultationInput, ctx: Context | None = None
) -> FedlexResponse:
    """Detail zu einer Vernehmlassung anhand ihrer eventId."""
    tool = "fedlex_get_consultation"
    lang = params.language.value
    today = today_in_zurich()
    retrieved_at = consultations.now_iso()
    event_id = params.event_id
    await _trace(ctx, tool, lang=lang, event_id=event_id)

    query = consultations.build_detail_query(lang, event_id)

    async with _tool_span(tool, lang=lang, event_id=event_id):
        try:
            bindings = await run_sparql(query)

            if not bindings:
                md = (
                    f"Keine Vernehmlassung mit eventId **{event_id}** gefunden [{lang.upper()}]."
                    + no_match_hint(
                        "**Tipps:** eventId prüfen (Form 'proj/JAHR/NR/cons_N') | "
                        "mit `fedlex_search_consultations` nach dem Titel suchen."
                    )
                )
                return _empty(tool, md, source=ATTRIBUTION_FEDLEX)

            r, has_subtask = consultations.record_from_detail(
                bindings, event_id, lang, today, retrieved_at
            )
            record = r.model_dump(mode="json")

            beginn = r.opened_on.isoformat() if r.opened_on else "–"
            frist = r.deadline.isoformat() if r.deadline else None
            md = f"## Vernehmlassung: {r.title}\n\n"
            md += "| Feld | Wert |\n|---|---|\n"
            md += f"| **eventId** | `{event_id}` |\n"
            md += f"| **Status (abgeleitet)** | {r.status} |\n"
            if r.status_source and r.status_source != r.status:
                md += f"| **Status (Quelle)** | {r.status_source} |\n"
            md += f"| **Eröffnet (eventStartDate)** | {beginn} |\n"
            if frist:
                md += f"| **Frist (eventEndDate)** | {frist} |\n"
                md += f"| **days_remaining** | {r.days_remaining} |\n"
            else:
                md += "| **Frist (eventEndDate)** | – (keine Frist hinterlegt) |\n"
            md += f"| **Federführendes Departement** | {r.lead_department or '–'} |\n"
            md += f"| **Federführendes Amt** | {r.lead_office or '–'} |\n"
            md += f"| **Status-Frist-Konflikt** | {'⚠️ ja' if r.status_conflict else 'nein'} |\n"
            md += f"| **retrieved_at** | {retrieved_at} |\n"
            md += f"\n**Direktlink:** [{r.source_url}]({r.source_url})\n"
            if r.description:
                md += f"\n**Beschreibung:** {r.description}\n"
            if not has_subtask:
                md += (
                    "\n> ℹ️ Zu dieser Vernehmlassung ist keine Teilaufgabe (hasSubTask) "
                    "hinterlegt — daher keine Frist, keine Federführung, keine Unterlagen "
                    "(48 von 2553 Consultations betroffen).\n"
                )
            if r.status_conflict:
                md += (
                    "\n> ⚠️ **status_conflict:** Quell-Status und Frist widersprechen sich. "
                    "Massgebend ist die Frist (eventEndDate), nicht der Status.\n"
                )
            if r.draft_documents:
                md += f"\n### 📎 Vernehmlassungsunterlagen ({len(r.draft_documents)})\n"
                for d in r.draft_documents:
                    md += f"- [{d['url']}]({d['url']})\n"
            if r.related_legal_resource:
                md += "\n### 🔗 Betroffene Rechtsressource\n"
                for i in r.related_legal_resource:
                    md += f"- [{i['url']}]({i['url']})\n"
            md += f"\n---\n*{ATTRIBUTION_FEDLEX}*"
            return _ok(tool, [record], md, source=ATTRIBUTION_FEDLEX)

        except Exception as e:
            return await _fail(ctx, tool, e, source=ATTRIBUTION_FEDLEX)


# ---------------------------------------------------------------------------
# Tools — TERMDAT (LINDAS, isoliert)
# ---------------------------------------------------------------------------


@mcp.tool(
    name="termdat_lookup_term",
    description=(
        "Schlägt einen Fachbegriff in TERMDAT nach und liefert die Entsprechungen "
        "in den anderen Landessprachen (de/fr/it/rm/en) samt Definition.\n"
        "<use_case>«Wie heisst dieser Begriff auf Französisch/Italienisch?» — amtliche "
        "Terminologie der Bundeskanzlei, z.B. für mehrsprachige Stellungnahmen.</use_case>\n"
        "<important_notes>Datenquelle ist der LINDAS-Teilbestand von TERMDAT: 77'692 von "
        "~400'000 Einträgen. Ein Negativtreffer heisst NICHT, dass der Begriff in TERMDAT "
        "fehlt, sondern nur, dass er nicht im publizierten Linked-Data-Teil liegt. "
        "'rm' ist im Teilbestand praktisch leer.</important_notes>\n"
        "<example>term='Volksschule', target_languages=['fr','it']</example>"
    ),
    annotations={
        "title": "Fachbegriff in TERMDAT nachschlagen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def termdat_lookup_term(
    params: TermdatLookupInput, ctx: Context | None = None
) -> FedlexResponse:
    """Begriff → Entsprechungen in de/fr/it/rm/en inkl. Definition (TERMDAT/LINDAS)."""
    tool = "termdat_lookup_term"
    langs = [lang.value for lang in params.target_languages]
    await _trace(ctx, tool, term_len=len(params.term), targets=",".join(langs))

    esc = sparql_escape(params.term.lower())
    # Schritt 1: passende Einträge (Konzept ODER Synonym-Variante) über den Namen.
    match_query = f"""
PREFIX schema: <http://schema.org/>
SELECT DISTINCT ?s ?name WHERE {{
  GRAPH <{LINDAS_GRAPH}> {{
    ?s a <{TERMDAT_TERM_TYPE}> ; schema:name ?name .
    FILTER(LCASE(STR(?name)) = "{esc}")
  }}
}}
LIMIT 100
"""

    async with _tool_span(tool, targets=",".join(langs)):
        try:
            matches = await run_lindas(match_query)

            if not matches:
                msg = (
                    f"Kein TERMDAT-Eintrag für «{params.term}» im LINDAS-Teilbestand "
                    f"({TERMDAT_LINDAS_ENTRIES:,} von ~{TERMDAT_COMMUNICATED_ENTRIES:,} "
                    "Einträgen). Das schliesst nicht aus, dass der Begriff in TERMDAT "
                    "existiert — er ist nur nicht als Linked Data publiziert."
                ).replace(",", "'")
                md = f"## TERMDAT — «{params.term}»\n\n{msg}" + no_match_hint(
                    "**Tipps:** exakte Schreibweise/Grossschreibung prüfen | Synonym versuchen | "
                    "auf www.termdat.bk.admin.ch nachschlagen."
                )
                return _termdat_empty(tool, md, message=msg)

            # Schritt 2: Match-URIs auf Konzept-IDs normalisieren (Quirk 3).
            concept_ids: list[str] = []
            for b in matches:
                cid = termdat_concept_id(val(b, "s"))
                if cid and cid not in concept_ids:
                    concept_ids.append(cid)
            concept_ids = concept_ids[: params.limit]
            if not concept_ids:
                md = f"## TERMDAT — «{params.term}»\n\nTreffer ohne auflösbare Konzept-ID."
                return _termdat_empty(tool, md)
            values_uris = " ".join(f"<{termdat_concept_uri(c)}>" for c in concept_ids)

            lang_filter = ", ".join(f'"{lang}"' for lang in langs)
            detail_query = f"""
PREFIX schema: <http://schema.org/>
SELECT ?c ?id ?name ?nl ?desc ?dl WHERE {{
  GRAPH <{LINDAS_GRAPH}> {{
    VALUES ?c {{ {values_uris} }}
    ?c schema:name ?name . BIND(LANG(?name) AS ?nl)
    OPTIONAL {{ ?c schema:identifier ?id . }}
    OPTIONAL {{ ?c schema:description ?desc . BIND(LANG(?desc) AS ?dl) }}
    FILTER(?nl IN ({lang_filter}))
  }}
}}
"""
            rows = await run_lindas(detail_query)

            # Pro Konzept Namen/Definitionen je Sprache dedupliziert sammeln
            # (name × description erzeugt ein Kreuzprodukt).
            concepts: dict[str, dict] = {}
            for b in rows:
                curi = val(b, "c")
                cid = termdat_concept_id(curi) or curi
                c = concepts.setdefault(cid, {"names": {}, "descriptions": {}, "uri": curi})
                nl, name = val(b, "nl"), val(b, "name")
                if nl and name:
                    c["names"].setdefault(nl, name)
                dl, desc = val(b, "dl"), val(b, "desc")
                if dl and desc:
                    c["descriptions"].setdefault(dl, desc)

            if not concepts:
                md = f"## TERMDAT — «{params.term}»\n\nEintrag gefunden, aber keine Namen in den Zielsprachen {langs}."
                return _termdat_empty(tool, md)

            results: list[dict] = []
            md = result_header(len(concepts), f"TERMDAT «{params.term}» → {', '.join(langs)}")
            for cid in concept_ids:
                if cid not in concepts:
                    continue
                c = concepts[cid]
                names = {lang: c["names"].get(lang) for lang in langs}
                url = termdat_entry_url(cid)
                results.append({
                    "concept_id": cid,
                    "names": names,
                    "descriptions": c["descriptions"],
                    "uri": c["uri"],
                    "url": url,
                })
                headline = c["names"].get("de") or next(iter(c["names"].values()), params.term)
                md += f"### {headline}  ·  TERMDAT {cid}\n"
                for lang in langs:
                    if names.get(lang):
                        md += f"- **{lang.upper()}:** {names[lang]}\n"
                definition = c["descriptions"].get("de") or next(iter(c["descriptions"].values()), None)
                if definition:
                    md += f"- **Definition:** {definition}\n"
                md += f"- **Eintrag:** [{url}]({url})\n\n"
            return _termdat_ok(tool, results, md)

        except Exception as e:
            return await _fail(ctx, tool, e, service="TERMDAT (LINDAS)",
                               source=ATTRIBUTION_TERMDAT, license=TERMDAT_LICENSE)


@mcp.tool(
    name="termdat_get_concept",
    description=(
        "Ruft den vollständigen TERMDAT-Eintrag zu einer ID oder URI ab.\n"
        "<use_case>Vollbild eines Terminologie-Konzepts: alle Sprachbenennungen, "
        "Definitionen, Synonyme und Quellenangaben.</use_case>\n"
        "<important_notes>Akzeptiert ID ('40109'), Konzept-URI oder Term-URI mit "
        "Sprachsuffix ('…/40109/3/de') und normalisiert intern (Quirk 3). Quelle ist der "
        "LINDAS-Teilbestand (77'692 von ~400'000 Einträgen).</important_notes>\n"
        "<example>concept='40109'</example>"
    ),
    annotations={
        "title": "TERMDAT-Eintrag vollständig abrufen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def termdat_get_concept(
    params: TermdatGetConceptInput, ctx: Context | None = None
) -> FedlexResponse:
    """Vollständiger TERMDAT-Eintrag zu einer URI oder ID (LINDAS)."""
    tool = "termdat_get_concept"
    await _trace(ctx, tool, raw_len=len(params.concept))

    cid = termdat_concept_id(params.concept)
    if cid is None:
        md = (
            f"Ungültige TERMDAT-Referenz: **{params.concept}**."
            + no_match_hint(
                "**Erwartet:** eine ID wie '40109', eine URI "
                "'https://register.ld.admin.ch/termdat/40109' oder eine Term-URI "
                "'…/termdat/40109/3/de'."
            )
        )
        return _termdat_empty(tool, md)

    curi = termdat_concept_uri(cid)
    async with _tool_span(tool, concept_id=cid):
        try:
            detail_query = f"""
PREFIX schema: <http://schema.org/>
SELECT ?name ?nl ?desc ?dl ?url ?mod WHERE {{
  GRAPH <{LINDAS_GRAPH}> {{
    <{curi}> schema:name ?name . BIND(LANG(?name) AS ?nl)
    OPTIONAL {{ <{curi}> schema:description ?desc . BIND(LANG(?desc) AS ?dl) }}
    OPTIONAL {{ <{curi}> schema:URL ?url . }}
    OPTIONAL {{ <{curi}> schema:dateModified ?mod . }}
  }}
}}
"""
            syn_query = f"""
PREFIX schema: <http://schema.org/>
SELECT ?syn ?name ?nl WHERE {{
  GRAPH <{LINDAS_GRAPH}> {{
    <{curi}> schema:hasPart ?syn .
    ?syn schema:name ?name . BIND(LANG(?name) AS ?nl)
  }}
}} ORDER BY ?syn
"""
            rows = await run_lindas(detail_query)
            if not rows:
                msg = (
                    f"Kein TERMDAT-Konzept mit ID {cid} im LINDAS-Teilbestand "
                    f"({TERMDAT_LINDAS_ENTRIES:,} von ~{TERMDAT_COMMUNICATED_ENTRIES:,})."
                ).replace(",", "'")
                md = f"## TERMDAT {cid}\n\n{msg}" + no_match_hint(
                    "**Tipps:** ID prüfen | ggf. auf www.termdat.bk.admin.ch nachschlagen."
                )
                return _termdat_empty(tool, md, message=msg)

            names: dict[str, str] = {}
            descriptions: dict[str, str] = {}
            web_url = termdat_entry_url(cid)
            modified = None
            for b in rows:
                nl, name = val(b, "nl"), val(b, "name")
                if nl and name:
                    names.setdefault(nl, name)
                dl, desc = val(b, "dl"), val(b, "desc")
                if dl and desc:
                    descriptions.setdefault(dl, desc)
                web_url = val(b, "url") or web_url
                modified = modified or (val(b, "mod") or None)

            syn_rows = await run_lindas(syn_query)
            synonyms = [
                {"name": val(b, "name"), "language": val(b, "nl") or None, "uri": val(b, "syn")}
                for b in syn_rows if val(b, "name")
            ]

            record = {
                "concept_id": cid,
                "names": names,
                "descriptions": descriptions,
                "synonyms": synonyms,
                "date_modified": modified,
                "uri": curi,
                "url": web_url,
            }

            headline = names.get("de") or next(iter(names.values()), f"TERMDAT {cid}")
            md = f"## TERMDAT {cid}: {headline}\n\n"
            md += "### Benennungen\n"
            for lang in ("de", "fr", "it", "rm", "en"):
                if names.get(lang):
                    md += f"- **{lang.upper()}:** {names[lang]}\n"
            if descriptions:
                md += "\n### Definitionen\n"
                for lang in ("de", "fr", "it", "rm", "en"):
                    if descriptions.get(lang):
                        md += f"- **{lang.upper()}:** {descriptions[lang]}\n"
            if synonyms:
                md += f"\n### Synonyme / Varianten ({len(synonyms)})\n"
                for s in synonyms:
                    lc = f" [{s['language']}]" if s["language"] else ""
                    md += f"- {s['name']}{lc}\n"
            if modified:
                md += f"\n_Zuletzt geändert: {modified}_\n"
            md += f"\n**Eintrag:** [{web_url}]({web_url})\n"
            return _termdat_ok(tool, [record], md)

        except Exception as e:
            return await _fail(ctx, tool, e, service="TERMDAT (LINDAS)",
                               source=ATTRIBUTION_TERMDAT, license=TERMDAT_LICENSE)


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


@mcp.resource("fedlex://sr/{sr_number}")
async def get_sr_resource(sr_number: str) -> str:
    """Ressource: Erlass der SR per SR-Nummer (Deutsch). Liefert die
    menschenlesbare Markdown-Aufbereitung aus dem Tool-Envelope."""
    resp = await fedlex_get_law_by_sr(
        GetLawBySrInput(sr_number=sr_number, language=Language.DE)
    )
    return resp.markdown


@mcp.resource("fedlex://info")
async def get_server_info() -> str:
    """Ressource: Metadaten und Capabilities des Fedlex MCP Servers."""
    return json.dumps(
        {
            "name": "Fedlex MCP Server",
            "version": "1.2.0",
            "description": (
                "Zugriff auf das Schweizer Bundesrecht, Vernehmlassungen (Fedlex) "
                "und die Terminologiedatenbank TERMDAT (LINDAS) via SPARQL"
            ),
            "endpoints": {
                "fedlex": SPARQL_ENDPOINT,
                "lindas_termdat": LINDAS_ENDPOINT,
            },
            "data_source": FEDLEX_BASE_URL,
            "license": SOURCE_LICENSE,
            "tools": [
                "fedlex_search_laws",
                "fedlex_get_law_by_sr",
                "fedlex_get_recent_publications",
                "fedlex_get_upcoming_changes",
                "fedlex_search_gazette",
                "fedlex_get_law_history",
                "fedlex_search_treaties",
                "fedlex_get_open_consultations",
                "fedlex_search_consultations",
                "fedlex_get_consultation",
                "termdat_lookup_term",
                "termdat_get_concept",
            ],
            "languages": ["de", "fr", "it", "rm", "en"],
            "data_model": (
                "JOLux Ontology — jolux:ConsolidationAbstract + jolux:Expression + "
                "jolux:Consultation; schema.org (schema.ld.admin.ch) für TERMDAT"
            ),
            "isolation": (
                "Getrennte httpx-Clients/Timeouts für Fedlex und LINDAS; ein "
                "LINDAS-Ausfall beeinträchtigt die fedlex_*-Tools nicht (ARCH A)."
            ),
            "termdat_note": ATTRIBUTION_TERMDAT,
        },
        ensure_ascii=False,
        indent=2,
    )


# ---------------------------------------------------------------------------
# Tool-Definition-Hash (SEC-022) — Rug-Pull-/Tool-Poisoning-Schutz
# ---------------------------------------------------------------------------


async def compute_tool_signature_hash() -> str:
    """SHA-256 über die stabilen Tool-Definitionen (Name, Beschreibung, Input-/
    Output-Schema, Annotations). Bei jeder absichtlichen Änderung muss das
    eingecheckte `tool-definitions.lock.json` neu erzeugt werden — eine
    stillschweigende Tool-Mutation (Rug Pull) fällt dadurch im Test auf."""
    tools = await mcp.list_tools()
    payload: list[dict[str, Any]] = []
    for t in sorted(tools, key=lambda x: x.name):
        ann = getattr(t, "annotations", None)
        payload.append({
            "name": t.name,
            "description": t.description,
            "inputSchema": t.input_schema,
            "outputSchema": getattr(t, "output_schema", None),
            # by_alias keeps the wire spelling (readOnlyHint, ...): mcp_types
            # 2.x renamed the Python fields to snake_case, and a bare dump
            # would silently change this hash without any contract change.
            "annotations": (
                ann.model_dump(mode="json", by_alias=True) if ann is not None else None
            ),
        })
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Tool-Allow-List (SEC-014) — Server-Side Defense-in-Depth, default-deny
# ---------------------------------------------------------------------------


def _apply_tool_allowlist() -> None:
    """Schränkt die exponierten Tools auf eine Allow-List ein (SEC-014).

    Standard ist «alle Tools». Wird `FEDLEX_ENABLED_TOOLS` (kommagetrennt)
    gesetzt, werden ausschliesslich die gelisteten Tools registriert
    (default-deny): nicht gelistete Tools verschwinden aus `tools/list` und
    sind nicht aufrufbar. Ergänzt — ersetzt nicht — ein vorgelagertes Gateway.
    """
    raw = os.environ.get("FEDLEX_ENABLED_TOOLS", "").strip()
    if not raw:
        return
    enabled = {name.strip() for name in raw.split(",") if name.strip()}
    try:
        registry = mcp._tool_manager._tools
        removed = [name for name in list(registry) if name not in enabled]
        for name in removed:
            registry.pop(name, None)
        log.info("tool_allowlist_applied", enabled=sorted(enabled), removed=sorted(removed))
    except Exception:  # pragma: no cover - interne MCPServer-API nicht verfügbar
        log.warning("tool_allowlist_unsupported")


_apply_tool_allowlist()


# ---------------------------------------------------------------------------
# Entry point — Dual Transport (Settings-/Env-gesteuert, ARCH-004 / SCALE-001)
# ---------------------------------------------------------------------------


def resolve_http_bind(argv: list[str] | None = None) -> tuple[str, int]:
    """Ermittelt Host/Port für den HTTP-Transport.

    Eigene Funktion, weil der Bind jetzt zwei Abnehmer hat — uvicorn *und* die
    App (siehe :func:`build_transport_security`). Vorher wurde er erst *nach*
    dem App-Bau berechnet, weshalb er dort gar nicht ankommen konnte.
    """
    argv = sys.argv if argv is None else argv
    host = os.environ.get("FEDLEX_HOST", settings.host)
    port = settings.port
    for i, arg in enumerate(argv):
        if arg == "--port" and i + 1 < len(argv):
            port = int(argv[i + 1])
    # Cloud-Plattformen (Render etc.) geben den Port via $PORT vor.
    return host, int(os.environ.get("PORT", port))


def build_transport_security(host: str, port: int):
    """Host/Origin-Allow-List für den Streamable-HTTP-Transport (SEC-005).

    Unter mcp 2.x ein per-App-Kwarg — und ihn wegzulassen ist nicht neutral: das
    SDK leitet aus dem ``host``-Argument der App einen Default ab und aktiviert
    bei loopback-artigem Wert automatisch ``127.0.0.1:*``. Da ``host`` selbst auf
    ``127.0.0.1`` defaultet, traf das jeden Start mit ``FEDLEX_HOST=0.0.0.0``:
    jede Anfrage unter einem echten Hostnamen bekam HTTP 421. Vor der Migration
    auf 2.x ging ``host`` an den ``FastMCP``-Konstruktor, wo dieselbe Logik den
    echten Bind sah und den Schutz korrekt ausliess.

    Rückgabe ``None``, wenn keine Allow-List ableitbar ist — Nicht-Loopback-Bind
    ohne ``FEDLEX_ALLOWED_HOSTS``. Eine geratene Liste reproduziert genau dieses
    421, der Aufrufer warnt stattdessen.
    """
    from mcp.server.transport_security import TransportSecuritySettings

    loopback = {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}
    allowed = [h.strip() for h in settings.allowed_hosts.split(",") if h.strip()]
    if allowed:
        # Loopback bleibt für Container-Health-Checks und Debugging erreichbar.
        hosts = set(allowed) | loopback
    elif host in ("127.0.0.1", "localhost", "::1"):
        hosts = loopback | {f"{host}:{port}"}
    else:
        return None

    # Konfigurierte CORS-Origins müssen auch die Transport-Prüfung passieren,
    # sonst weist der Server genau die Browser-Clients ab, die CORS erlaubt.
    # ``*`` ist nicht ausdrückbar (Origins werden literal verglichen).
    origins = {
        o.strip()
        for o in settings.allowed_origins.split(",")
        if o.strip() and o.strip() != "*"
    }
    origins |= {f"http://{h}" for h in hosts}
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=sorted(hosts),
        allowed_origins=sorted(origins),
    )


def build_http_app(host: str = "127.0.0.1", port: int = 8000):
    """Baut die Streamable-HTTP-App mit CORS (SDK-004).

    CORS exponiert den `Mcp-Session-Id`-Header, ohne den Browser-basierte
    MCP-Clients keine Folge-Requests an dieselbe Session schicken können.

    ``host`` muss die Adresse sein, an die uvicorn tatsächlich bindet — siehe
    :func:`build_transport_security`.
    """
    from starlette.middleware.cors import CORSMiddleware

    origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]

    security = build_transport_security(host, port)
    if security is None:
        log.warning(
            "dns_rebinding_protection_off",
            host=host,
            hint="Bind ist nicht Loopback und FEDLEX_ALLOWED_HOSTS ist leer — "
            "setze die Variable auf die Hostnamen, unter denen dieser Server "
            "erreichbar ist, damit Host und Origin geprüft werden",
        )
    app = mcp.streamable_http_app(transport_security=security, host=host)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Mcp-Session-Id"],
        expose_headers=["Mcp-Session-Id"],
    )
    return app


def _run_http() -> None:
    """Startet den Streamable-HTTP-Transport."""
    import uvicorn

    host, port = resolve_http_bind()
    origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
    log.info("http_start", host=host, port=port, cors_origins=origins)
    uvicorn.run(build_http_app(host, port), host=host, port=port)


if __name__ == "__main__":
    use_http = settings.transport in ("streamable-http", "http", "sse") or "--http" in sys.argv
    if use_http:
        _run_http()
    else:
        mcp.run()
