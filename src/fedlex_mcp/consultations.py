"""
Vernehmlassungen — isolierte Logikschicht (getrennt von der SR-/AS-/BBl-Schicht)
================================================================================
Fedlex führt Bundes-Vernehmlassungen als ``jolux:Consultation`` im *selben*
SPARQL-Graphen wie SR/AS/BBl (live verifiziert 2026-07-20). Dieses Modul kapselt
ausschliesslich die vernehmlassungs-spezifische Logik:

  * die **zentrale Fristenberechnung** (``deadline_status`` / ``days_until``),
    zeitzonenbewusst (Europe/Zurich) und gegen ein zur Laufzeit ermitteltes
    «heute» — eine einzige, testbare Stelle;
  * das **abgeleitete** ``status``-Feld: sagt die Quelle «Laufend», liegt die
    Frist aber in der Vergangenheit, **gewinnt das Datum** (eine abgelaufene
    Vernehmlassung erscheint nie als laufend);
  * das typisierte ``Consultation``-Pydantic-Modell mit den Pflichtfeldern
    ``title, status, opened_on, deadline, days_remaining, lead_office,
    source_url, retrieved_at, language``;
  * die Query-Bausteine samt **thematischem Freitext-Filter**.

Bewusst netzwerk- und server-frei (nur ``sparql_client`` + Stdlib), damit die
Fristen-/Statuslogik ohne HTTP getestet werden kann. ``server.py`` führt die
SPARQL-Abfrage aus und baut den Envelope/Markdown.

Known findings (live 2026-07-20, siehe README / CHANGELOG):
  * ``jolux:Consultation`` hat **keine** Sachgebiets-/Klassifikations-Taxonomie
    — thematische Filterung ist ausschliesslich Freitext im Titel/Beschrieb.
  * SPARQL-Quirk: ``REGEX(LCASE(...), "a|b")`` liefert auf diesem Endpoint still
    **0** Treffer; Alternation daher über **OR-verkettetes ``CONTAINS``**.
  * ``eventEndDate`` ist ``xsd:date`` (reiner Kalendertag, keine Uhrzeit/TZ) →
    Frist endet am Kalendertag; Vergleich gegen «heute in Europe/Zurich».
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

from .sparql_client import binding_val, sparql_escape

# ---------------------------------------------------------------------------
# Zeitzone & Uhr — Fristen enden am Kalendertag in Europe/Zurich
# ---------------------------------------------------------------------------

ZURICH = ZoneInfo("Europe/Zurich")


def today_in_zurich() -> date:
    """Der heutige Kalendertag in Europe/Zurich — zur Laufzeit, nie gecacht.

    Einzige Quelle für «heute» in den Vernehmlassungs-Tools. Tests
    monkeypatchen diese Funktion (injizierbare Uhr), statt gegen die reale
    Systemzeit zu prüfen.
    """
    return datetime.now(ZURICH).date()


def now_iso() -> str:
    """`retrieved_at`-Zeitstempel (UTC, sekundengenau) für jede Response."""
    return datetime.now(UTC).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Status-Vokabular (live verifiziert gegen .../vocabulary/consultation-status/)
# ---------------------------------------------------------------------------

CONSULTATION_STATUS_BASE = "https://fedlex.data.admin.ch/vocabulary/consultation-status/"
CONSULTATION_STATUS_RUNNING = CONSULTATION_STATUS_BASE + "2"
CONSULTATION_STATUS_LABELS = {
    CONSULTATION_STATUS_BASE + "0": "In Vorbereitung",
    CONSULTATION_STATUS_BASE + "1": "Geplant",
    CONSULTATION_STATUS_BASE + "2": "Laufend",
    CONSULTATION_STATUS_BASE + "3": "Abgeschlossen – abwarten Stellungnahmen und/oder des Ergebnisberichts",
    CONSULTATION_STATUS_BASE + "4": "Abgeschlossen – abwarten Ergebnisbericht",
    CONSULTATION_STATUS_BASE + "5": "Abgeschlossen",
    CONSULTATION_STATUS_BASE + "6": "Zurückgezogen",
}
CONSULTATION_STATUS_ALIASES = {
    "in_preparation": CONSULTATION_STATUS_BASE + "0",
    "planned": CONSULTATION_STATUS_BASE + "1",
    "running": CONSULTATION_STATUS_BASE + "2",
    "closed_awaiting_opinions": CONSULTATION_STATUS_BASE + "3",
    "closed_awaiting_report": CONSULTATION_STATUS_BASE + "4",
    "closed": CONSULTATION_STATUS_BASE + "5",
    "withdrawn": CONSULTATION_STATUS_BASE + "6",
}

# Abgeleitete Status-Labels — DATUMSgetrieben, unabhängig vom Quellfeld.
DERIVED_RUNNING = "Laufend"
DERIVED_CLOSED = "Abgeschlossen"

# ---------------------------------------------------------------------------
# Thematischer Filter — Freitext-Stichwort-Unions (in der Antwort ausgewiesen)
# ---------------------------------------------------------------------------
# Fedlex-Consultations tragen KEINE Sachgebiets-Taxonomie (live verifiziert).
# Thematische Filterung ist daher reine Freitextsuche. Die Unions sind bewusst
# breit gewählt: Ein Frühwarnsystem mit zu engem Filter warnt nicht, es beruhigt
# fälschlich. Relevante Vorlagen heissen «Berufsbildung», «Weiterbildung» oder
# «Hochschule», ohne das Wort «Schule» zu enthalten — der Ankerbegriff
# «Volksschule» selbst findet im Titel 0 Treffer.
TOPIC_KEYWORDS: dict[str, list[str]] = {
    "education": [
        "bildung", "schule", "berufsbildung", "weiterbildung", "hochschul",
        "lehrplan", "lehrmittel", "lehrperson", "pädagog", "kindergarten",
        "matur", "studien", "unterricht",
    ],
}


def effective_terms(topic: str | None, keyword: str | None) -> list[str]:
    """Die tatsächlich gesuchten Stichwörter (lowercase, dedupliziert).

    Union aus der Themen-Stichwortliste (falls ``topic``) und dem freien
    ``keyword``. Reihenfolge stabil, damit die Ausweisung in der Antwort
    reproduzierbar ist.
    """
    terms: list[str] = []
    if topic:
        terms.extend(TOPIC_KEYWORDS.get(topic, []))
    if keyword:
        terms.append(keyword.lower())
    seen: set[str] = set()
    out: list[str] = []
    for t in terms:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def describe_filter(topic: str | None, terms: list[str]) -> str | None:
    """Menschenlesbare Ausweisung der Filterstrategie (wonach *nicht* gesucht
    wurde, wird dadurch explizit). ``None``, wenn ungefiltert."""
    if not terms:
        return None
    base = f"Themenfilter «{topic}»: " if topic else "Stichwortfilter: "
    return (
        base
        + "Titel enthält eines von [" + ", ".join(terms) + "] "
        + "(Freitextsuche im Titel — keine Sachgebiets-Taxonomie vorhanden)."
    )


# ---------------------------------------------------------------------------
# Zentrale Fristen-/Statuslogik (pur, testbar)
# ---------------------------------------------------------------------------


def parse_date(value: str | None) -> date | None:
    """Parst ein ``xsd:date`` (``YYYY-MM-DD``) defensiv; ``None`` bei Fehlen/
    Unparsbarkeit statt einer Exception."""
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def days_until(deadline: date | None, today: date) -> int | None:
    """Verbleibende Kalendertage bis (einschliesslich) zum Fristtag.

    ``0`` = Frist endet heute, negativ = bereits abgelaufen, ``None`` = keine
    Frist hinterlegt. Kalendertag-Semantik (Europe/Zurich), kein 24-h-Fenster.
    """
    if deadline is None:
        return None
    return (deadline - today).days


def deadline_status(
    deadline: date | None, status_uri: str | None, today: date
) -> tuple[str, bool, bool]:
    """Leitet ``(status, is_open, status_conflict)`` ab — **die Frist gewinnt**.

    * Mit Frist: laufend genau dann, wenn ``deadline >= today`` (Fristtag
      inklusive). Danach «Abgeschlossen», egal was das Quellfeld sagt.
    * Ohne Frist: keine Ableitung aus dem Datum möglich → Rückfall auf das
      Quell-Label (z.B. «Geplant», «In Vorbereitung»); ``is_open=False``.
    * ``status_conflict`` ist ``True``, wenn Quellfeld und Frist sich
      widersprechen (Quelle «Laufend», Frist abgelaufen — oder umgekehrt).
    """
    if deadline is None:
        label = CONSULTATION_STATUS_LABELS.get(status_uri or "", "unbekannt")
        return label, False, False
    is_open = deadline >= today
    derived = DERIVED_RUNNING if is_open else DERIVED_CLOSED
    if status_uri:
        source_running = status_uri == CONSULTATION_STATUS_RUNNING
        conflict = source_running != is_open
    else:
        conflict = False
    return derived, is_open, conflict


# ---------------------------------------------------------------------------
# Typisiertes Modell (Pflichtfelder gemäss Spezifikation)
# ---------------------------------------------------------------------------


class Consultation(BaseModel):
    """Strukturierter Vernehmlassungs-Datensatz.

    Pflichtfelder (immer vorhanden, ggf. ``None``): ``title, status,
    opened_on, deadline, days_remaining, lead_office, source_url,
    retrieved_at, language``. ``status`` ist der **abgeleitete** Status
    (Datum gewinnt); ``status_source`` bewahrt das rohe Quell-Label.
    """

    model_config = ConfigDict(extra="forbid")

    event_id: str | None = None
    title: str
    status: str
    status_source: str | None = None
    status_uri: str | None = None
    status_conflict: bool = False
    is_open: bool = False
    opened_on: date | None = None
    deadline: date | None = None
    days_remaining: int | None = None
    lead_department: str | None = None
    lead_office: str | None = None
    language: str
    source_url: str | None = None
    uri: str | None = None
    retrieved_at: str
    # Nur in der Detailansicht belegt:
    description: str | None = None
    draft_documents: list[dict] = Field(default_factory=list)
    related_legal_resource: list[dict] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# URL-Helfer
# ---------------------------------------------------------------------------

FEDLEX_BASE_URL = "https://www.fedlex.admin.ch"


def event_url(event_id: str, lang: str = "de") -> str:
    """fedlex.admin.ch-Link zu einem Vernehmlassungs-Projekt."""
    return f"{FEDLEX_BASE_URL}/eli/dl/{event_id}/{lang}"


def _data_url(uri: str, lang: str) -> str:
    if uri.startswith("https://fedlex.data.admin.ch/"):
        return f"{FEDLEX_BASE_URL}{uri.replace('https://fedlex.data.admin.ch', '')}/{lang}"
    return uri


# ---------------------------------------------------------------------------
# Query-Bausteine
# ---------------------------------------------------------------------------

_PREFIXES = (
    "PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>\n"
    "PREFIX skos: <http://www.w3.org/2004/02/skos/core#>\n"
    "PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>"
)


def _title_contains_any(terms: list[str]) -> str:
    """OR-verkettetes ``CONTAINS`` über den Titel (kein REGEX — Alternation ist
    auf diesem Endpoint kaputt, s. Modul-Docstring)."""
    if not terms:
        return ""
    clauses = " || ".join(
        f'CONTAINS(LCASE(STR(?title)), "{sparql_escape(t)}")' for t in terms
    )
    return f"FILTER({clauses})"


def _select_body(lang: str, *extra: str) -> str:
    """Gemeinsamer WHERE-Rumpf (Titel/Frist/Amt). Sprachfilter ``LANG(?title)``
    entfernt die DE/FR/IT-Dreifach-Duplikate (alle Vorlagen tragen einen
    de- und fr-Titel — der Filter verliert live 0 Vorlagen)."""
    tail = "\n  ".join(f for f in extra if f)
    return f"""
  ?c a jolux:Consultation ;
     jolux:eventId ?eventId ;
     jolux:eventTitle ?title .
  OPTIONAL {{ ?c jolux:consultationStatus ?status . }}
  OPTIONAL {{
    ?c jolux:hasSubTask ?t .
    OPTIONAL {{ ?t jolux:eventStartDate ?start . }}
    OPTIONAL {{ ?t jolux:eventEndDate ?end . }}
    OPTIONAL {{
      ?t jolux:institutionInChargeOfTheEvent ?inst .
      OPTIONAL {{ ?inst skos:prefLabel ?instLabel . FILTER(LANG(?instLabel) = "de") }}
    }}
    OPTIONAL {{
      ?t jolux:institutionInChargeOfTheEventLevel2 ?inst2 .
      OPTIONAL {{ ?inst2 skos:prefLabel ?inst2Label . FILTER(LANG(?inst2Label) = "de") }}
    }}
  }}
  FILTER(LANG(?title) = "{lang}")
  {tail}"""


def build_open_query(lang: str, terms: list[str], today: date, limit: int) -> str:
    """Offene Verfahren: **Frist-basiert** (``eventEndDate >= today``), sortiert
    nach kürzester Restfrist. Der Status wird bewusst NICHT gefiltert (die Frist
    ist massgebend)."""
    deadline_filter = f'FILTER(BOUND(?end) && xsd:date(?end) >= "{today.isoformat()}"^^xsd:date)'
    body = _select_body(lang, _title_contains_any(terms), deadline_filter)
    return f"""{_PREFIXES}
SELECT DISTINCT ?c ?eventId ?title ?status ?start ?end ?instLabel ?inst2Label WHERE {{
{body}
}} ORDER BY ASC(?end)
LIMIT {limit}
"""


def build_search_query(
    lang: str,
    terms: list[str],
    keyword_desc: str | None,
    status_uri: str | None,
    from_date: date | None,
    to_date: date | None,
    institution: str | None,
    limit: int,
) -> str:
    """Volltext-/Filtersuche (auch abgeschlossene Verfahren). ``keyword_desc``
    erweitert die Titelsuche zusätzlich auf ``eventDescription``."""
    filters: list[str] = []
    if terms:
        filters.append(_title_contains_any(terms))
    if keyword_desc:
        esc = sparql_escape(keyword_desc.lower())
        filters.append(
            'OPTIONAL { ?c jolux:eventDescription ?desc . FILTER(LANG(?desc) = "' + lang + '") }\n'
            f'  FILTER(CONTAINS(LCASE(STR(?title)), "{esc}") '
            f'|| CONTAINS(LCASE(STR(COALESCE(?desc, ""))), "{esc}"))'
        )
    if status_uri:
        filters.append(f"FILTER(?status = <{status_uri}>)")
    if from_date:
        filters.append(f'FILTER(BOUND(?end) && xsd:date(?end) >= "{from_date.isoformat()}"^^xsd:date)')
    if to_date:
        filters.append(f'FILTER(BOUND(?end) && xsd:date(?end) <= "{to_date.isoformat()}"^^xsd:date)')
    if institution:
        esc_inst = sparql_escape(institution.lower())
        filters.append(
            f'FILTER(CONTAINS(LCASE(STR(COALESCE(?instLabel, ?inst2Label, ""))), "{esc_inst}"))'
        )
    body = _select_body(lang, *filters)
    return f"""{_PREFIXES}
SELECT DISTINCT ?c ?eventId ?title ?status ?start ?end ?instLabel ?inst2Label WHERE {{
{body}
}} ORDER BY DESC(?eventId)
LIMIT {limit}
"""


def build_detail_query(lang: str, event_id: str) -> str:
    """Detail zu einer ``eventId`` (Frist, Amt, Unterlagen, Rechtsressource)."""
    esc_id = sparql_escape(event_id)
    return f"""{_PREFIXES}
SELECT ?c ?title ?desc ?status ?start ?end ?instLabel ?inst2Label ?draft ?impact WHERE {{
  ?c a jolux:Consultation ;
     jolux:eventId "{esc_id}" .
  OPTIONAL {{ ?c jolux:eventTitle ?title . FILTER(LANG(?title) = "{lang}") }}
  OPTIONAL {{ ?c jolux:eventDescription ?desc . FILTER(LANG(?desc) = "{lang}") }}
  OPTIONAL {{ ?c jolux:consultationStatus ?status . }}
  OPTIONAL {{ ?c jolux:foreseenImpactToLegalResource ?impact . }}
  OPTIONAL {{
    ?c jolux:hasSubTask ?t .
    OPTIONAL {{ ?t jolux:eventStartDate ?start . }}
    OPTIONAL {{ ?t jolux:eventEndDate ?end . }}
    OPTIONAL {{ ?t jolux:opinionHasDraftRelatedDocument ?draft . }}
    OPTIONAL {{
      ?t jolux:institutionInChargeOfTheEvent ?inst .
      OPTIONAL {{ ?inst skos:prefLabel ?instLabel . FILTER(LANG(?instLabel) = "de") }}
    }}
    OPTIONAL {{
      ?t jolux:institutionInChargeOfTheEventLevel2 ?inst2 .
      OPTIONAL {{ ?inst2 skos:prefLabel ?inst2Label . FILTER(LANG(?inst2Label) = "de") }}
    }}
  }}
}}
LIMIT 200
"""


# ---------------------------------------------------------------------------
# Binding → Modell
# ---------------------------------------------------------------------------


def record_from_binding(b: dict, lang: str, today: date, retrieved_at: str) -> Consultation:
    """Baut einen ``Consultation``-Datensatz aus einem Listen-Binding."""
    event_id = binding_val(b, "eventId") or None
    status_uri = binding_val(b, "status") or None
    deadline = parse_date(binding_val(b, "end"))
    opened = parse_date(binding_val(b, "start"))
    status, is_open, conflict = deadline_status(deadline, status_uri, today)
    return Consultation(
        event_id=event_id,
        title=binding_val(b, "title", "(kein Titel)"),
        status=status,
        status_source=(CONSULTATION_STATUS_LABELS.get(status_uri, None) if status_uri else None),
        status_uri=status_uri,
        status_conflict=conflict,
        is_open=is_open,
        opened_on=opened,
        deadline=deadline,
        days_remaining=days_until(deadline, today),
        lead_department=binding_val(b, "instLabel") or None,
        lead_office=binding_val(b, "inst2Label") or None,
        language=lang,
        source_url=event_url(event_id, lang) if event_id else None,
        uri=binding_val(b, "c") or None,
        retrieved_at=retrieved_at,
    )


def records_from_bindings(
    bindings: list[dict], lang: str, today: date, retrieved_at: str
) -> list[Consultation]:
    return [record_from_binding(b, lang, today, retrieved_at) for b in bindings]


def record_from_detail(
    bindings: list[dict], event_id: str, lang: str, today: date, retrieved_at: str
) -> tuple[Consultation, bool]:
    """Aggregiert die (wegen mehrfacher Unterlagen/Institutionen mehrzeiligen)
    Detail-Bindings zu **einem** Datensatz. Zweiter Rückgabewert: ob eine
    Teilaufgabe (``hasSubTask``) vorhanden ist."""
    first = bindings[0]

    def first_val(key: str) -> str | None:
        return next((binding_val(b, key) for b in bindings if binding_val(b, key)), None)

    title = first_val("title") or "(kein Titel)"
    desc = first_val("desc")
    status_uri = first_val("status") or None
    start = first_val("start")
    end = first_val("end")
    inst = first_val("instLabel")
    inst2 = first_val("inst2Label")
    drafts = sorted({binding_val(b, "draft") for b in bindings if binding_val(b, "draft")})
    impacts = sorted({binding_val(b, "impact") for b in bindings if binding_val(b, "impact")})

    deadline = parse_date(end)
    opened = parse_date(start)
    status, is_open, conflict = deadline_status(deadline, status_uri, today)
    has_subtask = bool(start or end or drafts or inst or inst2)

    record = Consultation(
        event_id=event_id,
        title=title,
        status=status,
        status_source=(CONSULTATION_STATUS_LABELS.get(status_uri, None) if status_uri else None),
        status_uri=status_uri,
        status_conflict=conflict,
        is_open=is_open,
        opened_on=opened,
        deadline=deadline,
        days_remaining=days_until(deadline, today),
        lead_department=inst,
        lead_office=inst2,
        language=lang,
        source_url=event_url(event_id, lang),
        uri=binding_val(first, "c") or None,
        retrieved_at=retrieved_at,
        description=desc,
        draft_documents=[{"uri": d, "url": _data_url(d, lang)} for d in drafts],
        related_legal_resource=[{"uri": i, "url": _data_url(i, lang)} for i in impacts],
    )
    return record, has_subtask
