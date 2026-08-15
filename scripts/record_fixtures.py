#!/usr/bin/env python3
"""Zeichnet echte SPARQL-Antworten nach `tests/fixtures/` auf.

Warum: eine handgeschriebene Fixture kodiert die Annahme ihres Autors und kann
sie deshalb nicht widerlegen. In `i14y-mcp` blieb genau deshalb eine ganze Suite
gruen, waehrend drei Tools produktiv leere Titel lieferten — die Stubs hatten
einen Schluessel erfunden und stimmten dem Mapper zu statt der Quelle.

Dieser Server spricht mit **zwei** Endpunkten (Fedlex und LINDAS/TERMDAT), aber
in einem Dutzend Abfrageformen. Die Form der Antwort haengt an der Abfrage und
nicht am Endpunkt: `fedlex_get_law_history` liefert andere Variablen als
`fedlex_search_treaties`, und ein Stub, der beide gleich raet, faellt nie auf.
Aufgezeichnet wird deshalb eine Antwort **je Abfrage**, die ein Werkzeug
abschickt — auch dann, wenn ein Werkzeug mehrere abschickt.

**Aufgezeichnet wird an der Naht, an der der Server die Antwort erhaelt.** Der
Recorder faehrt die Werkzeuge selbst und schneidet `_execute_sparql` mit; die
Fixture ist damit per Konstruktion die Antwort auf die Abfrage, die der Server
wirklich stellt. Eine von Hand nachgebaute Abfrage waere schon wieder eine
Annahme.

Herkunft, Datum, Auswahlregel und SHA-256 je Datei schreibt dieses Skript nach
`tests/fixtures/PROVENANCE.md`. Neu aufzeichnen:

    PYTHONPATH=src python scripts/record_fixtures.py

Braucht Netzzugang zu `fedlex.data.admin.ch` und `lindas.admin.ch`.
Entwicklungswerkzeug; weder das Paket noch die Testsuite importieren es.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from fedlex_mcp import server as s
from fedlex_mcp import sparql_client

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"

# Fest gewaehlte Eingaben, nicht «irgendwelche»: eine vom Lauf abhaengige
# Auswahl erzeugt bei jedem Aufzeichnen einen anderen Diff. SR 235.1 ist das
# Datenschutzgesetz — dasselbe Gesetz in `get_law_by_sr` und `get_law_history`,
# damit die beiden Aufzeichnungen denselben Gegenstand beschreiben.
SR_NUMMER = "235.1"
SUCHBEGRIFF = "Datenschutz"
GAZETTE_BEGRIFF = "Bildung"
STAATSVERTRAG_BEGRIFF = "Bildung"
TERMDAT_BEGRIFF = "Volksschule"
LIMIT = 3


def _faelle() -> list[tuple[str, str, Any]]:
    """(Dateiname-Praefix, Werkzeugname, Eingabe) je Werkzeug."""
    return [
        ("search_laws", "fedlex_search_laws", s.SearchLawsInput(keywords=SUCHBEGRIFF, limit=LIMIT)),
        ("law_by_sr", "fedlex_get_law_by_sr", s.GetLawBySrInput(sr_number=SR_NUMMER)),
        (
            "recent_publications",
            "fedlex_get_recent_publications",
            s.GetRecentPublicationsInput(days=30, limit=LIMIT),
        ),
        ("upcoming_changes", "fedlex_get_upcoming_changes", s.GetUpcomingChangesInput()),
        (
            "gazette",
            "fedlex_search_gazette",
            s.SearchGazetteInput(keywords=GAZETTE_BEGRIFF, limit=LIMIT),
        ),
        ("law_history", "fedlex_get_law_history", s.GetLawHistoryInput(sr_number=SR_NUMMER)),
        (
            "treaties",
            "fedlex_search_treaties",
            s.SearchTreatiesInput(keywords=STAATSVERTRAG_BEGRIFF, limit=LIMIT),
        ),
        ("open_consultations", "fedlex_get_open_consultations", s.GetOpenConsultationsInput()),
        ("termdat_lookup", "termdat_lookup_term", s.TermdatLookupInput(term=TERMDAT_BEGRIFF)),
    ]


async def main() -> int:
    logging.disable(logging.CRITICAL)  # das Tool-Logging gehoert nicht in den Lauf
    FIXTURES.mkdir(parents=True, exist_ok=True)
    recorded_at = datetime.now(UTC).strftime("%Y-%m-%d")
    entries: list[dict[str, Any]] = []
    print(f"Zeichne auf von {s.SPARQL_ENDPOINT} und {s.LINDAS_ENDPOINT}")

    echt = sparql_client.get_bindings
    mitschnitt: list[tuple[str, str, str]] = []

    async def aufzeichnend(
        client: httpx.AsyncClient, endpoint: str, query: str, **kw: Any
    ) -> list[dict]:
        """Ruft durch und schneidet die **echte** Antwort mit.

        `get_bindings` liefert geparste Bindings; aufgezeichnet werden soll die
        Antwort, wie sie ankommt — der Parser gehoert zu dem, was geprueft
        werden soll.

        Mitgeschnitten wird ueber einen Antwort-Hook am Client, nicht ueber
        eine zweite, selbst gestellte Anfrage. Die erste Fassung tat das
        Letztere und bekam kein JSON zurueck: die Anfrage des Clients traegt
        einen `Accept`-Header, den ich beim Nachstellen vergessen hatte. Genau
        die Sorte Abweichung, wegen der aufgezeichnet statt nachgebaut wird.
        """
        gesehen: list[str] = []

        async def hook(response: httpx.Response) -> None:
            await response.aread()
            gesehen.append(response.text)

        client.event_hooks.setdefault("response", []).append(hook)
        try:
            bindings = await echt(client, endpoint, query, **kw)
        finally:
            client.event_hooks["response"].remove(hook)
        assert gesehen, "kein Antwort-Hook ausgeloest"
        mitschnitt.append((endpoint, query, gesehen[-1]))
        return bindings

    sparql_client.get_bindings = aufzeichnend  # type: ignore[assignment]
    try:
        for praefix, werkzeug, eingabe in _faelle():
            # Wiederholen, weil die Endpunkte sporadisch die Verbindung
            # abbrechen. Der Server faengt das ab und antwortet degradiert --
            # dann kommt hier keine Abfrage an, und ein Abbruch des ganzen
            # Laufs hinterliesse einen halben Fixture-Ordner samt Nachweis, der
            # ihn nicht mehr beschreibt.
            for versuch in range(4):
                mitschnitt.clear()
                ergebnis = await getattr(s, werkzeug)(eingabe)
                if mitschnitt:
                    break
                print(f"      {werkzeug}: keine Abfrage angekommen, Versuch {versuch + 2}/4 ...")
                await asyncio.sleep(3.0 * (versuch + 1))
            treffer = len((ergebnis.model_dump() or {}).get("results") or [])
            assert mitschnitt, (
                f"{werkzeug} hat nach vier Anlaeufen keine Abfrage abgeschickt — "
                "Endpunkt erreichbar?"
            )
            for i, (endpoint, query, text) in enumerate(mitschnitt):
                name = f"{praefix}.json" if len(mitschnitt) == 1 else f"{praefix}_{i + 1}.json"
                zeilen = len(json.loads(text).get("results", {}).get("bindings", []))
                blob = text.encode("utf-8")
                (FIXTURES / name).write_bytes(blob)
                entries.append(
                    {
                        "name": name,
                        "werkzeug": werkzeug,
                        "endpoint": endpoint,
                        "eingabe": repr(eingabe.model_dump()),
                        "schritt": f"{i + 1} von {len(mitschnitt)}",
                        "bytes": len(blob),
                        "zeilen": zeilen,
                        "treffer": treffer,
                        "sha256": hashlib.sha256(blob).hexdigest(),
                    }
                )
                print(f"  ok  {name:<28} {len(blob):>7} B  ({zeilen} Zeilen)")
    finally:
        sparql_client.get_bindings = echt  # type: ignore[assignment]

    leer = [e["name"] for e in entries if e["zeilen"] == 0]
    if leer:
        print(f"\n!! leere Aufzeichnungen: {leer}")
        print("   Eine leere Fixture sieht aus wie eine gueltige und prueft nichts.")

    # Altlasten entfernen: aendert ein Werkzeug die Zahl seiner Abfragen, heisst
    # die Datei anders (`law_by_sr.json` wird zu `law_by_sr_1.json`), und die
    # alte bliebe sonst liegen -- eine Aufzeichnung ohne Aufzeichner, die
    # aussieht wie eine gueltige. Genau das ist beim ersten Lauf passiert.
    geschrieben = {e["name"] for e in entries} | {"PROVENANCE.md"}
    for pfad in sorted(FIXTURES.iterdir()):
        if pfad.is_file() and pfad.name not in geschrieben:
            pfad.unlink()
            print(f"  weg {pfad.name:<28} (nicht mehr Teil des Laufs)")

    _write_provenance(recorded_at, entries)
    print(f"\nPROVENANCE.md geschrieben, Aufzeichnungsdatum {recorded_at}")
    return _warne_bei_ignorierten(entries) or (1 if leer else 0)


def _warne_bei_ignorierten(entries: list[dict[str, Any]]) -> int:
    """Meldet Aufzeichnungen, die `.gitignore` ausschliesst.

    Eine ignorierte Fixture faellt lokal nicht auf — die Datei liegt ja da und
    die Suite ist gruen. Erst die CI klont ein Repo ohne sie und wird rot, mit
    einer Fehlermeldung, die nach einem Aufzeichnungsproblem aussieht statt nach
    einer Regel in `.gitignore`. In `swiss-housing-mcp` ist genau das passiert.
    """
    pfade = [str(FIXTURES / e["name"]) for e in entries]
    try:
        ergebnis = subprocess.run(
            ["git", "check-ignore", *pfade], capture_output=True, text=True, check=False
        )
    except OSError:
        return 0
    ignoriert = [z for z in ergebnis.stdout.splitlines() if z.strip()]
    if ignoriert:
        print("\n!! Diese Aufzeichnungen schliesst .gitignore aus, sie fehlen der CI:")
        for z in ignoriert:
            print(f"     {z}")
        return 1
    return 0


def _write_provenance(recorded_at: str, entries: list[dict[str, Any]]) -> None:
    lines = [
        "# Herkunft der Fixtures",
        "",
        "**Erzeugt von `scripts/record_fixtures.py`. Nicht von Hand pflegen.**",
        "",
        f"Aufgezeichnet am **{recorded_at}** von den beiden Endpunkten dieses",
        f"Servers: `{s.SPARQL_ENDPOINT}` und `{s.LINDAS_ENDPOINT}`.",
        "",
        "Ohne Datum ist «aufgezeichnet» nach zwei Jahren von «ausgedacht» nicht",
        "mehr zu unterscheiden — die Datei sieht gleich aus.",
        "",
        "**Zwei Endpunkte, ein Dutzend Abfrageformen.** Die Form der Antwort",
        "haengt hier an der Abfrage und nicht am Endpunkt: `get_law_history`",
        "liefert andere Variablen als `search_treaties`. Die Portfolio-Regel",
        "«eine Antwort je externem Endpunkt» waere mit zwei Dateien erfuellt und",
        "truege fast nichts; aufgezeichnet ist deshalb eine Antwort je Abfrage,",
        "die ein Werkzeug abschickt — auch dann, wenn ein Werkzeug mehrere",
        "abschickt (dann durchnummeriert).",
        "",
        "**Aufgezeichnet an der Naht, an der der Server die Antwort erhaelt.**",
        "Der Recorder faehrt die Werkzeuge selbst und schneidet die",
        "SPARQL-Schicht mit. Die Fixture ist damit per Konstruktion die Antwort",
        "auf die Abfrage, die der Server wirklich stellt — eine von Hand",
        "nachgebaute Abfrage waere schon wieder eine Annahme.",
        "",
        "**Aufgezeichnet ist die rohe SPARQL-JSON-Antwort**, nicht die geparsten",
        "Bindings. Der Parser gehoert zu dem, was geprueft werden soll.",
        "",
        "`get_law_by_sr` und `get_law_history` fragen **dasselbe** Gesetz ab",
        f"(SR {SR_NUMMER}), damit die beiden Aufzeichnungen einen Gegenstand",
        "beschreiben und nicht zwei.",
        "",
        "Fehlerpfade — Timeouts, 5xx, eine kaputte Abfrage — bleiben",
        "handgeschrieben. Die lassen sich nicht auf Zuruf aufzeichnen.",
        "",
    ]
    for e in entries:
        lines += [
            f"## `{e['name']}`",
            "",
            f"- **Werkzeug:** `{e['werkzeug']}` (Abfrage {e['schritt']})",
            f"- **Endpunkt:** `{e['endpoint']}`",
            f"- **Eingabe:** `{e['eingabe']}`",
            f"- **Aufgezeichnet:** {recorded_at}",
            f"- **Groesse:** {e['bytes']} B ({e['zeilen']} Ergebniszeilen, "
            f"{e['treffer']} Treffer im Werkzeug)",
            f"- **SHA-256:** `{e['sha256']}`",
            "",
        ]
    (FIXTURES / "PROVENANCE.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
