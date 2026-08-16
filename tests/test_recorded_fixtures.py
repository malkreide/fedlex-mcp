"""Jede Abfrage, gefahren aus einer aufgezeichneten Antwort.

Die handgeschriebenen Stubs im Rest der Suite pruefen die *Fehler*-Pfade — ein
Timeout, ein 5xx, eine leere Trefferliste —, die sich nicht auf Zuruf
aufzeichnen lassen und als Erfindung in Ordnung sind. Was sie nicht koennen: die
Form einer Erfolgs-Antwort belegen. Sie stimmen mit dem ueberein, was ihr Autor
annahm.

Dieser Server spricht mit **zwei** Endpunkten, aber in einem Dutzend
Abfrageformen. Aufgezeichnet ist deshalb eine Antwort je Abfrage, die ein
Werkzeug abschickt — auch dann, wenn ein Werkzeug mehrere abschickt.

Herkunft, Datum, Auswahlregel und SHA-256 je Datei stehen in
`tests/fixtures/PROVENANCE.md`; neu aufzeichnen mit
`PYTHONPATH=src python scripts/record_fixtures.py`.
"""

from __future__ import annotations

import datetime as dt
import json
import re

import httpx
import pytest
import respx

from fedlex_mcp import server
from tests.fixture_data import fixture_json, fixture_text, provenance, recorded_names

ENDPOINT = server.SPARQL_ENDPOINT
LINDAS = server.LINDAS_ENDPOINT

# Jedes Werkzeug, seine Eingabe und die Aufzeichnungen seiner Abfragen — in der
# Reihenfolge, in der es sie abschickt. Ein Werkzeug ohne Aufzeichnung faellt in
# `test_jedes_werkzeug_hat_eine_aufzeichnung`.
WERKZEUGE: dict[str, tuple[str, list[str]]] = {
    "fedlex_search_laws": ("SearchLawsInput", ["search_laws.json"]),
    "fedlex_get_law_by_sr": ("GetLawBySrInput", ["law_by_sr_1.json", "law_by_sr_2.json"]),
    "fedlex_get_recent_publications": (
        "GetRecentPublicationsInput",
        ["recent_publications.json"],
    ),
    "fedlex_get_upcoming_changes": ("GetUpcomingChangesInput", ["upcoming_changes.json"]),
    "fedlex_search_gazette": ("SearchGazetteInput", ["gazette.json"]),
    "fedlex_get_law_history": ("GetLawHistoryInput", ["law_history.json"]),
    "fedlex_search_treaties": ("SearchTreatiesInput", ["treaties.json"]),
    "fedlex_get_open_consultations": ("GetOpenConsultationsInput", ["open_consultations.json"]),
    "termdat_lookup_term": (
        "TermdatLookupInput",
        ["termdat_lookup_1.json", "termdat_lookup_2.json"],
    ),
}

EINGABEN = {
    "fedlex_search_laws": {"keywords": "Datenschutz", "limit": 3},
    "fedlex_get_law_by_sr": {"sr_number": "235.1"},
    "fedlex_get_recent_publications": {"days": 30, "limit": 3},
    "fedlex_get_upcoming_changes": {},
    "fedlex_search_gazette": {"keywords": "Bildung", "limit": 3},
    "fedlex_get_law_history": {"sr_number": "235.1"},
    "fedlex_search_treaties": {"keywords": "Bildung", "limit": 3},
    "fedlex_get_open_consultations": {},
    "termdat_lookup_term": {"term": "Volksschule"},
}


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Backoff auf null — geprueft wird die Form der Antwort, nicht die Wartezeit."""
    monkeypatch.setattr(server, "RETRY_BASE_DELAY", 0.0)


def _fahre(werkzeug: str):
    """Baut die Eingabe und ruft das Werkzeug — Eingabeklasse aus dem Modul."""
    klasse = getattr(server, WERKZEUGE[werkzeug][0])
    return getattr(server, werkzeug)(klasse(**EINGABEN[werkzeug]))


# --------------------------------------------------------------------------
# Herkunft
# --------------------------------------------------------------------------


def test_provenance_nennt_ein_brauchbares_aufnahmedatum():
    """Eine Aufzeichnung ohne Datum ist eine undatierte Behauptung ueber die Quelle."""
    match = re.search(r"Aufgezeichnet am \*\*(\d{4}-\d{2}-\d{2})\*\*", provenance())
    assert match, "PROVENANCE.md nennt kein Aufnahmedatum im erwarteten Format"
    when = dt.date.fromisoformat(match.group(1))
    assert when <= dt.datetime.now(dt.UTC).date(), "Aufnahmedatum liegt in der Zukunft"


def test_jede_fixture_steht_in_der_provenance():
    """Sonst waechst der Ordner und der Nachweis bleibt zurueck.

    Genau das ist beim ersten Lauf passiert: `fedlex_get_law_by_sr` schickt
    zwei Abfragen, und die Datei aus einem frueheren Lauf mit nur einer blieb
    liegen. Der Recorder raeumt jetzt auf; diese Zusicherung merkt es, wenn er
    es nicht tut.
    """
    text = provenance()
    fehlend = [n for n in recorded_names() if f"## `{n}`" not in text]
    assert not fehlend, f"ohne Eintrag in PROVENANCE.md: {fehlend}"


def test_jedes_werkzeug_hat_eine_aufzeichnung():
    """Bewacht die Regel selbst — hier je Abfrage statt je Endpunkt.

    Zwei Endpunkte, ein Dutzend Abfrageformen: die Regel «eine Antwort je
    externem Endpunkt» waere mit zwei Dateien erfuellt und truege fast nichts.
    """
    erwartet = {n for _, namen in WERKZEUGE.values() for n in namen}
    fehlend = sorted(erwartet - set(recorded_names()))
    assert not fehlend, f"Abfragen ohne Aufzeichnung: {fehlend}"


@pytest.mark.parametrize("name", sorted({n for _, namen in WERKZEUGE.values() for n in namen}))
def test_jede_aufzeichnung_traegt_bindings(name):
    """Eine leere Antwort sieht aus wie eine gueltige und prueft nichts."""
    bindings = fixture_json(name).get("results", {}).get("bindings", [])
    assert bindings, f"{name} traegt keine Bindings — neu aufzeichnen"


# --------------------------------------------------------------------------
# Die Werkzeuge, jedes an seiner eigenen Antwort
# --------------------------------------------------------------------------


@pytest.mark.parametrize("werkzeug", sorted(WERKZEUGE))
@respx.mock
async def test_jedes_werkzeug_liest_seine_aufgezeichnete_antwort(werkzeug):
    """Der eigentliche Punkt: jede Abfrage bekommt *ihre* Antwort.

    Alle mit derselben zu bedienen hiesse, die Aufzeichnung gegen eine Abfrage
    zu halten, die sie nicht beantwortet — genau der Fehler, den eine Fixture je
    Abfrage verhindern soll.
    """
    namen = WERKZEUGE[werkzeug][1]
    antworten = [httpx.Response(200, text=fixture_text(n)) for n in namen]
    respx.get(url__startswith=ENDPOINT).mock(side_effect=list(antworten))
    respx.get(url__startswith=LINDAS).mock(side_effect=list(antworten))

    ergebnis = await _fahre(werkzeug)
    daten = ergebnis.model_dump()
    assert daten.get("error") in (None, ""), daten.get("error")
    assert daten.get("results"), f"{werkzeug} liefert keine Treffer aus der Aufzeichnung"


def test_die_abfrageformen_tragen_verschiedene_variablen():
    """Der Grund, warum je Abfrage aufgezeichnet wird.

    Waeren die Antwortformen gleich, genuegte eine Datei. Sie sind es nicht:
    die Variablenmengen der Aufzeichnungen unterscheiden sich, und ein Stub,
    der sie gleich raet, faellt nie auf.
    """
    formen = {}
    for _, namen in WERKZEUGE.values():
        for n in namen:
            kopf = fixture_json(n).get("head", {}).get("vars", [])
            formen[n] = frozenset(kopf)
    assert len(set(formen.values())) > 1, "alle Aufzeichnungen tragen dieselben Variablen"
    # Und keine ist leer — eine Antwort ohne Variablen belegt keine Form.
    for n, vars_ in formen.items():
        assert vars_, f"{n} nennt keine Variablen im Kopf"


def test_gesetz_und_historie_beschreiben_dasselbe_gesetz():
    """Zwei Werkzeuge, ein Gegenstand — sonst belegen zwei Dateien zwei Dinge.

    Der Recorder fragt beide mit derselben SR-Nummer ab. Zwei erfundene
    Fixtures haetten hier leicht zwei verschiedene Gesetze gezeigt, ohne dass es
    jemandem auffiele.
    """
    nachweis = provenance()
    assert nachweis.count("'sr_number': '235.1'") >= 2, (
        "die beiden SR-Abfragen sollen dieselbe Nummer tragen"
    )
    hist = fixture_json("law_history.json")["results"]["bindings"]
    detail = fixture_json("law_by_sr_1.json")["results"]["bindings"]
    assert hist and detail


@respx.mock
async def test_termdat_geht_an_den_anderen_endpunkt():
    """TERMDAT liegt auf LINDAS, nicht auf Fedlex — zwei Endpunkte, ein Server.

    Diese Zusicherung liest die tatsaechlich gestellte Anfrage. Ginge die
    Terminologie-Abfrage an den Fedlex-Endpunkt, kaeme sie leer zurueck und
    saehe wie ein Negativtreffer aus.
    """
    antworten = [
        httpx.Response(200, text=fixture_text("termdat_lookup_1.json")),
        httpx.Response(200, text=fixture_text("termdat_lookup_2.json")),
    ]
    lindas_route = respx.get(url__startswith=LINDAS).mock(side_effect=antworten)
    fedlex_route = respx.get(url__startswith=ENDPOINT).mock(
        return_value=httpx.Response(200, text=fixture_text("search_laws.json"))
    )
    await _fahre("termdat_lookup_term")
    assert lindas_route.called, "die Terminologie-Abfrage gehoert an LINDAS"
    assert not fedlex_route.called, "sie darf nicht an den Fedlex-Endpunkt gehen"


def test_die_aufzeichnungen_nennen_beide_endpunkte():
    """Sonst belegt der Ordner nur die Haelfte des Servers."""
    nachweis = provenance()
    assert ENDPOINT in nachweis
    assert LINDAS in nachweis


@respx.mock
async def test_ein_leeres_ergebnis_bleibt_ein_leeres_ergebnis():
    """Die Gegenrichtung, und sie ist die wichtigere Haelfte.

    `bindings: []` ist eine Aussage der Quelle: es gibt dazu nichts. Das darf
    nicht als Fehler herauskommen — sonst kann das Modell einen echten
    Negativtreffer nicht von einem Ausfall unterscheiden.
    """
    leer = json.dumps({"head": {"vars": ["ca"]}, "results": {"bindings": []}})
    respx.get(url__startswith=ENDPOINT).mock(return_value=httpx.Response(200, text=leer))
    ergebnis = await _fahre("fedlex_search_laws")
    daten = ergebnis.model_dump()
    assert not daten.get("results")
    assert not daten.get("error"), "eine leere Suche ist kein Fehler"


# --------------------------------------------------------------------------
# Der Nachweis, nachgerechnet
# --------------------------------------------------------------------------
@pytest.mark.parametrize("name", sorted(n for n in recorded_names() if n != "PROVENANCE.md"))
def test_die_pruefsumme_im_nachweis_stimmt(name):
    """Eine Pruefsumme, die niemand nachrechnet, ist Zierde.

    Sie steht im Nachweis, um genau einen Fall zu fangen: eine Aufzeichnung,
    die nach dem Lauf von Hand nachgebessert wurde. Eine korrigierte Antwort
    ist wieder eine erfundene — und von aussen ist ihr das nicht anzusehen.
    Ohne diesen Test faengt die Summe nichts.

    Gerechnet wird ueber die Bytes auf der Platte, nicht ueber den Loader:
    genau die hat der Recorder gehasht, und ein Loader, der unterwegs dekodiert
    oder normalisiert, wuerde die Pruefung gegen sich selbst fuehren.
    """
    import hashlib
    import re
    from pathlib import Path

    teile = provenance().split(f"## `{name}`", 1)
    assert len(teile) == 2, f"{name} hat keinen Block in PROVENANCE.md"
    treffer = re.search(r"\*\*SHA-256:\*\*\s*`([0-9a-f]{64})`", teile[1].split("## ", 1)[0])
    assert treffer, f"{name} steht ohne Pruefsumme im Nachweis"
    roh = (Path(__file__).resolve().parent / "fixtures" / name).read_bytes()
    assert hashlib.sha256(roh).hexdigest() == treffer.group(1), (
        f"{name} weicht vom Nachweis ab — von Hand nachgebessert? Neu aufzeichnen."
    )
