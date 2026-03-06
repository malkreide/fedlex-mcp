"""
Fedlex MCP Server
=================
MCP server für das Schweizer Bundesrecht via den Fedlex SPARQL-Endpoint.
Ermöglicht Zugriff auf die Systematische Rechtssammlung (SR), Amtliche
Sammlung (AS), Bundesblatt (BBl) und Staatsverträge.

Datenquelle: https://fedlex.data.admin.ch
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

Transport: Dual — stdio (lokal) und SSE (Cloud/Render.com)
"""

import json
import os
from datetime import date, timedelta
from enum import Enum
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Konstanten
# ---------------------------------------------------------------------------

SPARQL_ENDPOINT = "https://fedlex.data.admin.ch/sparqlendpoint"
FEDLEX_BASE_URL = "https://www.fedlex.admin.ch"
REQUEST_TIMEOUT = 45
MAX_RESULTS_DEFAULT = 20
MAX_RESULTS_LIMIT = 100

LANG_SUFFIX = {"de": "/de", "fr": "/fr", "it": "/it", "rm": "/rm"}

STATUS_IN_FORCE = "https://fedlex.data.admin.ch/vocabulary/enforcement-status/0"
STATUS_NOT_PUBLISHED = "https://fedlex.data.admin.ch/vocabulary/enforcement-status/1"
STATUS_NO_LONGER_FORCE = "https://fedlex.data.admin.ch/vocabulary/enforcement-status/3"

STATUS_LABELS = {
    STATUS_IN_FORCE: "✅ In Kraft",
    STATUS_NOT_PUBLISHED: "⚠️ Nicht mehr in SR publiziert",
    STATUS_NO_LONGER_FORCE: "❌ Nicht mehr in Kraft",
}

FEDLEX_SOURCE = "\n---\n*Quelle: Fedlex, Schweizerische Bundeskanzlei (fedlex.admin.ch)*"

# ---------------------------------------------------------------------------
# Server-Initialisierung
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "fedlex_mcp",
    instructions=(
        "MCP-Server für das Schweizer Bundesrecht (Fedlex). "
        "Zugriff auf die Systematische Rechtssammlung (SR), "
        "Amtliche Sammlung (AS), Bundesblatt (BBl) und Staatsverträge. "
        "Alle Daten stammen vom SPARQL-Endpoint der Schweizerischen Bundeskanzlei."
    ),
)

# ---------------------------------------------------------------------------
# Geteilte Infrastruktur
# ---------------------------------------------------------------------------


class Language(str, Enum):
    """Offizielle Landessprachen der Schweizerischen Eidgenossenschaft."""

    DE = "de"
    FR = "fr"
    IT = "it"
    RM = "rm"


async def run_sparql(query: str) -> list[dict]:
    """Führt SPARQL-Abfrage gegen den Fedlex-Endpoint aus, gibt Bindings zurück."""
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.get(
            SPARQL_ENDPOINT,
            params={"query": query, "format": "application/sparql-results+json"},
            headers={"Accept": "application/sparql-results+json"},
        )
        response.raise_for_status()
        return response.json().get("results", {}).get("bindings", [])


def val(binding: dict, key: str, default: str = "") -> str:
    """Extrahiert sicher den String-Wert aus einem SPARQL-Binding."""
    entry = binding.get(key)
    return entry.get("value", default) if entry else default


def fedlex_url(uri: str, lang: str = "de") -> str:
    """Wandelt Fedlex-Daten-URI in lesbare fedlex.admin.ch-URL um."""
    if uri.startswith("https://fedlex.data.admin.ch/"):
        path = uri.replace("https://fedlex.data.admin.ch", "")
        return f"{FEDLEX_BASE_URL}{path}/{lang}"
    return uri


def status_label(status_uri: str) -> str:
    """Gibt lesbares Label für einen Enforcement-Status-URI zurück."""
    return STATUS_LABELS.get(status_uri, f"({status_uri.split('/')[-1]})")


def handle_error(e: Exception) -> str:
    """Einheitliche, handlungsweisende Fehlermeldungen."""
    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        if code == 400:
            return "Fehler: Ungültige SPARQL-Abfrage (HTTP 400). Suchparameter überprüfen."
        if code == 429:
            return "Fehler: Rate Limit erreicht. Bitte kurz warten und erneut versuchen."
        if code == 503:
            return "Fehler: Fedlex vorübergehend nicht verfügbar. Später erneut versuchen."
        return f"Fehler: HTTP {code} vom Fedlex-Endpoint."
    if isinstance(e, (httpx.TimeoutException, httpx.ReadTimeout)):
        return (
            "Fehler: Timeout beim Fedlex-Endpoint. "
            "Komplexe SPARQL-Abfragen können länger dauern — bitte erneut versuchen."
        )
    if isinstance(e, httpx.ConnectError):
        return "Fehler: Verbindung zu Fedlex fehlgeschlagen. Internetverbindung prüfen."
    return f"Fehler: {type(e).__name__}: {e}"


def result_header(count: int, desc: str) -> str:
    """Standardisierter Ergebnisheader."""
    return f"## Fedlex — {desc}\n**Treffer:** {count}\n\n"


# ---------------------------------------------------------------------------
# Input-Modelle
# ---------------------------------------------------------------------------


class SearchLawsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    keywords: str = Field(
        ...,
        description="Suchbegriff(e) im Erlasstittel, z.B. 'Volksschule', 'Datenschutz', 'Berufsbildung'",
        min_length=2, max_length=200,
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
        min_length=1, max_length=20,
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
        min_length=2, max_length=200,
    )
    language: Language = Field(default=Language.DE)
    year: Optional[int] = Field(default=None, ge=1999, le=2030,
                                description="Optional: Nur dieses Publikationsjahr (z.B. 2024)")
    limit: int = Field(default=MAX_RESULTS_DEFAULT, ge=1, le=MAX_RESULTS_LIMIT)


class GetLawHistoryInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    sr_number: str = Field(
        ...,
        description="SR-Nummer, z.B. '235.1' (DSG), '412.10' (BBG), '101' (BV)",
        min_length=1, max_length=20,
    )
    language: Language = Field(default=Language.DE)


class SearchTreatiesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    keywords: Optional[str] = Field(
        default=None,
        description="Suchbegriff im Titel, z.B. 'Bildung', 'EU', 'Datenschutz'. Ohne Begriff: neueste Verträge.",
        max_length=200,
    )
    language: Language = Field(default=Language.DE)
    limit: int = Field(default=MAX_RESULTS_DEFAULT, ge=1, le=MAX_RESULTS_LIMIT)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool(
    name="fedlex_search_laws",
    annotations={
        "title": "Erlasse der Systematischen Rechtssammlung (SR) suchen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def fedlex_search_laws(params: SearchLawsInput) -> str:
    """Durchsucht die Systematische Rechtssammlung (SR) des Bundes nach Erlasstiteln.

    Sucht in allen konsolidierten Bundeserlassen (Gesetze, Verordnungen, Vereinbarungen)
    nach einem Stichwort im Titel. Gibt SR-Nummer, Abkürzung, Status und Link zurück.
    Mit in_force_only=True (Standard) werden nur gültige Erlasse gezeigt.

    Args:
        params (SearchLawsInput): Suchparameter:
            - keywords (str): Suchbegriff im Titel (z.B. 'Volksschule', 'Datenschutz')
            - language (Language): Sprache ('de', 'fr', 'it', 'rm'). Standard: 'de'
            - in_force_only (bool): Nur gültige Erlasse. Standard: True
            - limit (int): Maximale Trefferzahl (1–100). Standard: 20

    Returns:
        str: Markdown-Liste mit SR-Nummer, Titel, Abkürzung, Status und Link
    """
    lang = params.language.value
    suffix = LANG_SUFFIX[lang]
    kw = params.keywords.lower()

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
  FILTER(CONTAINS(LCASE(STR(?title)), "{kw}"))
  {in_force_filter}
}} ORDER BY ?srNumber
LIMIT {params.limit}
"""

    try:
        bindings = await run_sparql(query)

        if not bindings:
            return (
                f"Keine Erlasse für **'{params.keywords}'** gefunden "
                f"[{lang.upper()}, nur gültige: {params.in_force_only}].\n\n"
                "**Tipps:** Allgemeineren Begriff verwenden | "
                "`in_force_only=false` für aufgehobene Erlasse | "
                "Auf Deutsch suchen (vollständigste Abdeckung)"
            )

        out = result_header(len(bindings), f"SR-Suche '{params.keywords}' [{lang.upper()}]")
        for b in bindings:
            uri = val(b, "ca")
            title = val(b, "title", "(kein Titel)")
            short = val(b, "titleShort")
            sr_num = val(b, "srNumber", "–")
            status_uri = val(b, "inForceStatus")
            st = status_label(status_uri) if status_uri else "–"
            url = fedlex_url(uri, lang)

            short_display = f" ({short})" if short else ""
            out += f"### SR {sr_num}: {title}{short_display}\n"
            out += f"- **Status:** {st}\n"
            out += f"- **Link:** [{url}]({url})\n\n"

        out += FEDLEX_SOURCE
        return out

    except Exception as e:
        return handle_error(e)


def _format_law_detail(
    b: dict, sr: str, lang: str, suffix: str, successor: dict | None = None,
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
        out += f"\n---\n### ⚠️ Nachfolge-Erlass (in Kraft)\n\n"
        out += "| Feld | Wert |\n|---|---|\n"
        out += f"| **Vollständiger Titel** | {s_title} |\n"
        out += f"| **Abkürzung** | {s_short} |\n"
        if s_sr != "–":
            out += f"| **SR-Nummer** | {s_sr} |\n"
        out += f"| **Inkrafttreten** | {s_entry} |\n"
        out += f"| **Status** | ✅ In Kraft |\n"
        out += f"\n**Direktlink:** [{s_url}]({s_url})\n"

    out += FEDLEX_SOURCE
    return out


@mcp.tool(
    name="fedlex_get_law_by_sr",
    annotations={
        "title": "Erlass nach SR-Nummer abrufen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def fedlex_get_law_by_sr(params: GetLawBySrInput) -> str:
    """Ruft einen Bundeserlass anhand seiner SR-Nummer ab (Detailansicht).

    Gibt vollständige Metadaten zurück: Titel, Abkürzung, Status,
    Inkrafttretungsdatum und Link zum konsolidierten Text.

    Args:
        params (GetLawBySrInput):
            - sr_number (str): SR-Nummer (z.B. '101', '235.1', '412.10')
            - language (Language): Sprache der Metadaten. Standard: 'de'

    Returns:
        str: Markdown-Detailblatt mit allen verfügbaren Metadaten
    """
    lang = params.language.value
    suffix = LANG_SUFFIX[lang]
    sr = params.sr_number.strip()

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
  FILTER(STR(?srNumber) = "{sr}")
}} ORDER BY DESC(?entryDate)
LIMIT 10
"""

    try:
        bindings = await run_sparql(query)

        if not bindings:
            return (
                f"Kein Erlass mit SR-Nummer **{sr}** gefunden [{lang.upper()}].\n\n"
                "**Mögliche Ursachen:**\n"
                "- SR-Nummer falsch (Punkt als Trennzeichen: '235.1', nicht '235,1')\n"
                "- Erlass in dieser Sprache nicht vorhanden\n"
                "- Erlass aufgehoben (mit `in_force_only=false` in `fedlex_search_laws` suchen)"
            )

        # Bevorzuge den gültigen Erlass (In Kraft) gegenüber aufgehobenen Fassungen,
        # da mehrere ConsolidationAbstract-Einträge dieselbe SR-Nummer teilen können
        # (z.B. altes DSG von 1992 und revidiertes nDSG von 2020 unter SR 235.1).
        in_force = [b for b in bindings if val(b, "inForceStatus") == STATUS_IN_FORCE]
        b = in_force[0] if in_force else bindings[0]
        status_uri = val(b, "inForceStatus")

        # Wenn der Erlass nicht mehr in Kraft ist, Nachfolge-Erlass suchen.
        # Einige revidierte Erlasse (z.B. nDSG 2020) haben in Fedlex keine
        # historicalLegalId, sind aber über den Kurztitel (titleShort) auffindbar.
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
  FILTER(STR(?titleShort) = "{short_name}")
}} LIMIT 1
"""
                succ_bindings = await run_sparql(succ_query)
                if succ_bindings:
                    successor = succ_bindings[0]

        return _format_law_detail(b, sr, lang, suffix, successor)

    except Exception as e:
        return handle_error(e)


@mcp.tool(
    name="fedlex_get_recent_publications",
    annotations={
        "title": "Neueste Bundesrechtspublikationen (AS) abrufen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def fedlex_get_recent_publications(params: GetRecentPublicationsInput) -> str:
    """Ruft die neuesten Publikationen der Amtlichen Sammlung (AS) und des BBl ab.

    Die AS enthält alle neuen und geänderten Bundeserlasse bei erstmaliger
    Veröffentlichung. Ideal für regelmässiges Monitoring von Rechtsänderungen.

    Args:
        params (GetRecentPublicationsInput):
            - days (int): Letzte N Tage (1–365). Standard: 30
            - language (Language): Sprache. Standard: 'de'
            - limit (int): Maximale Trefferzahl. Standard: 20

    Returns:
        str: Markdown-Liste der neuesten Publikationen mit Datum und Link
    """
    lang = params.language.value
    suffix = LANG_SUFFIX[lang]
    since_date = (date.today() - timedelta(days=params.days)).isoformat()

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

    try:
        bindings = await run_sparql(query)

        if not bindings:
            return (
                f"Keine Publikationen in den letzten {params.days} Tagen gefunden "
                f"[{lang.upper()}].\n\n**Tipp:** `days` erhöhen, z.B. `days=90`."
            )

        out = result_header(len(bindings), f"AS-Publikationen seit {since_date} [{lang.upper()}]")
        for b in bindings:
            uri = val(b, "act")
            title = val(b, "title", "(kein Titel)")
            pub_date = val(b, "pubDate", "–")
            url = fedlex_url(uri, lang)
            out += f"### {pub_date}\n**{title}**\n[{url}]({url})\n\n"

        out += FEDLEX_SOURCE
        return out

    except Exception as e:
        return handle_error(e)


@mcp.tool(
    name="fedlex_get_upcoming_changes",
    annotations={
        "title": "Bevorstehende Rechtsänderungen abrufen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def fedlex_get_upcoming_changes(params: GetUpcomingChangesInput) -> str:
    """Ruft Erlasse ab, die in den nächsten N Tagen in Kraft treten.

    Proaktives Rechtsmonitoring für Verwaltung und Schulen: Welche Gesetze
    werden bald wirksam? Z.B. neue Datenschutzregeln, Bildungsgesetze,
    Regulierungen, auf die man sich vorbereiten muss.

    Args:
        params (GetUpcomingChangesInput):
            - days_ahead (int): Vorausschau in Tagen (1–365). Standard: 90
            - language (Language): Sprache. Standard: 'de'
            - limit (int): Maximale Trefferzahl. Standard: 20

    Returns:
        str: Markdown-Liste bevorstehender Rechtsänderungen, chronologisch
             mit SR-Nummer, Inkrafttretungsdatum und Link
    """
    lang = params.language.value
    suffix = LANG_SUFFIX[lang]
    today = date.today().isoformat()
    future = (date.today() + timedelta(days=params.days_ahead)).isoformat()

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

    try:
        bindings = await run_sparql(query)

        if not bindings:
            return (
                f"Keine bevorstehenden Rechtsänderungen in den nächsten "
                f"{params.days_ahead} Tagen [{lang.upper()}].\n\n"
                "**Tipp:** `days_ahead` erhöhen, z.B. `days_ahead=180`."
            )

        out = result_header(
            len(bindings), f"Bevorstehende Änderungen bis {future} [{lang.upper()}]"
        )
        for b in bindings:
            uri = val(b, "ca")
            title = val(b, "title", "(kein Titel)")
            short = val(b, "titleShort")
            sr_num = val(b, "srNumber", "–")
            entry = val(b, "entryDate", "–")
            url = fedlex_url(uri, lang)

            short_display = f" ({short})" if short else ""
            sr_display = f"SR {sr_num}" if sr_num != "–" else "SR –"
            out += f"### 📅 {entry} — {sr_display}: {title}{short_display}\n"
            out += f"[{url}]({url})\n\n"

        out += FEDLEX_SOURCE
        return out

    except Exception as e:
        return handle_error(e)


@mcp.tool(
    name="fedlex_search_gazette",
    annotations={
        "title": "Im Bundesblatt (BBl) suchen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def fedlex_search_gazette(params: SearchGazetteInput) -> str:
    """Durchsucht das Bundesblatt (BBl) nach amtlichen Publikationen.

    Das BBl ist das offizielle Amtsblatt des Bundes: Botschaften des Bundesrates,
    Parlamentsinitiativen, Volksinitiativanträge, Vernehmlassungsankündigungen
    und weitere Bekanntmachungen. Nützlich für politisches Frühwarnsystem.

    Args:
        params (SearchGazetteInput):
            - keywords (str): Suchbegriff im Publikationstitel
            - language (Language): Sprache. Standard: 'de'
            - year (Optional[int]): Nur dieses Jahr (z.B. 2024)
            - limit (int): Maximale Trefferzahl. Standard: 20

    Returns:
        str: Markdown-Liste der gefundenen BBl-Publikationen mit Datum und Link
    """
    lang = params.language.value
    suffix = LANG_SUFFIX[lang]
    kw = params.keywords.lower()

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
  FILTER(CONTAINS(LCASE(STR(?title)), "{kw}"))
  {year_filter}
}} ORDER BY DESC(?pubDate)
LIMIT {params.limit}
"""

    try:
        bindings = await run_sparql(query)

        yr_txt = f" ({params.year})" if params.year else ""
        if not bindings:
            return (
                f"Keine BBl-Publikation für **'{params.keywords}'**{yr_txt} "
                f"[{lang.upper()}].\n\n"
                "**Tipps:** Allgemeineren Begriff verwenden | "
                "Jahr weglassen | `fedlex_search_laws` für konsolidiertes Recht"
            )

        out = result_header(
            len(bindings), f"BBl-Suche '{params.keywords}'{yr_txt} [{lang.upper()}]"
        )
        for b in bindings:
            uri = val(b, "act")
            title = val(b, "title", "(kein Titel)")
            pub_date = val(b, "pubDate", "–")
            url = fedlex_url(uri, lang)
            out += f"### {pub_date}\n**{title}**\n[{url}]({url})\n\n"

        out += FEDLEX_SOURCE
        return out

    except Exception as e:
        return handle_error(e)


@mcp.tool(
    name="fedlex_get_law_history",
    annotations={
        "title": "Versionsgeschichte eines Erlasses abrufen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def fedlex_get_law_history(params: GetLawHistoryInput) -> str:
    """Ruft die Versionsgeschichte (alle konsolidierten Fassungen) eines Erlasses ab.

    Zeigt alle historischen Versionen mit Inkrafttretensdatum und Status.
    Z.B. für DSG 235.1: Wann galt die alte Fassung, wann trat die revidierte in Kraft?

    Args:
        params (GetLawHistoryInput):
            - sr_number (str): SR-Nummer (z.B. '235.1', '412.10', '101')
            - language (Language): Sprache. Standard: 'de'

    Returns:
        str: Markdown-Tabelle aller Versionen mit Datum, Status und Link
    """
    lang = params.language.value
    suffix = LANG_SUFFIX[lang]
    sr = params.sr_number.strip()

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
  FILTER(STR(?srNumber) = "{sr}")
}} ORDER BY DESC(?entryDate)
LIMIT 50
"""

    try:
        bindings = await run_sparql(query)

        if not bindings:
            return (
                f"Keine Versionsgeschichte für SR-Nummer **{sr}** [{lang.upper()}].\n\n"
                "**Tipp:** SR-Nummer mit `fedlex_get_law_by_sr` überprüfen."
            )

        title_sample = val(bindings[0], "title", sr)
        out = f"## Versionsgeschichte: {title_sample}\n"
        out += f"**SR {sr}** | {lang.upper()}\n\n"
        out += "| Fassung | Inkrafttreten | Status | Link |\n"
        out += "|---|---|---|---|\n"

        for i, b in enumerate(bindings):
            uri = val(b, "ca")
            entry = val(b, "entryDate", "–")
            status_uri = val(b, "inForceStatus")
            url = fedlex_url(uri, lang)
            st = status_label(status_uri) if status_uri else "–"
            out += f"| v{len(bindings) - i} | {entry} | {st} | [→]({url}) |\n"

        out += FEDLEX_SOURCE
        return out

    except Exception as e:
        return handle_error(e)


@mcp.tool(
    name="fedlex_search_treaties",
    annotations={
        "title": "Staatsverträge der Schweiz suchen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def fedlex_search_treaties(params: SearchTreatiesInput) -> str:
    """Sucht internationale Staatsverträge der Schweiz (SR-Nummern beginnen mit '0.').

    Umfasst bilaterale und multilaterale Abkommen: EU-Bilaterale, Doppelbesteuerungs-
    abkommen, Europarats-Konventionen (Datenschutz, Menschenrechte), Bildungsabkommen.

    Args:
        params (SearchTreatiesInput):
            - keywords (Optional[str]): Suchbegriff (z.B. 'Datenschutz', 'EU', 'Bildung')
            - language (Language): Sprache. Standard: 'de'
            - limit (int): Maximale Trefferzahl. Standard: 20

    Returns:
        str: Markdown-Liste der Staatsverträge mit SR-Nummer, Titel und Link
    """
    lang = params.language.value
    suffix = LANG_SUFFIX[lang]

    kw_filter = (
        f'FILTER(CONTAINS(LCASE(STR(?title)), "{params.keywords.lower()}"))'
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

    try:
        bindings = await run_sparql(query)

        kw_txt = f"'{params.keywords}'" if params.keywords else "alle"
        if not bindings:
            return (
                f"Keine Staatsverträge für {kw_txt} [{lang.upper()}].\n\n"
                "**Tipp:** Suchbegriff anpassen oder weglassen."
            )

        out = result_header(len(bindings), f"Staatsverträge {kw_txt} [{lang.upper()}]")
        for b in bindings:
            uri = val(b, "ca")
            title = val(b, "title", "(kein Titel)")
            sr_num = val(b, "srNumber", "–")
            entry = val(b, "entryDate", "–")
            url = fedlex_url(uri, lang)
            out += f"### SR {sr_num}: {title}\n"
            out += f"- **Inkrafttreten:** {entry}\n"
            out += f"- **Link:** [{url}]({url})\n\n"

        out += FEDLEX_SOURCE
        return out

    except Exception as e:
        return handle_error(e)


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


@mcp.resource("fedlex://sr/{sr_number}")
async def get_sr_resource(sr_number: str) -> str:
    """Ressource: Erlass der SR per SR-Nummer (Deutsch)."""
    return await fedlex_get_law_by_sr(
        GetLawBySrInput(sr_number=sr_number, language=Language.DE)
    )


@mcp.resource("fedlex://info")
async def get_server_info() -> str:
    """Ressource: Metadaten und Capabilities des Fedlex MCP Servers."""
    return json.dumps(
        {
            "name": "Fedlex MCP Server",
            "version": "1.0.0",
            "description": "Zugriff auf das Schweizer Bundesrecht via Fedlex SPARQL",
            "sparql_endpoint": SPARQL_ENDPOINT,
            "data_source": FEDLEX_BASE_URL,
            "license": "Freie Wiederverwendung (kommerziell und andere Zwecke)",
            "tools": [
                "fedlex_search_laws",
                "fedlex_get_law_by_sr",
                "fedlex_get_recent_publications",
                "fedlex_get_upcoming_changes",
                "fedlex_search_gazette",
                "fedlex_get_law_history",
                "fedlex_search_treaties",
            ],
            "languages": ["de", "fr", "it", "rm"],
            "data_model": "JOLux Ontology — jolux:ConsolidationAbstract + jolux:Expression",
        },
        ensure_ascii=False,
        indent=2,
    )


# ---------------------------------------------------------------------------
# Einstiegspunkt — Dual Transport
# ---------------------------------------------------------------------------

def main() -> None:
    """Einstiegspunkt für CLI-Installation via pip/uvx."""
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    port = int(os.environ.get("PORT", "8000"))

    if transport == "sse":
        mcp.run(transport="sse", port=port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
