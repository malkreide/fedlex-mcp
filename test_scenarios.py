"""
15 diverse Testszenarien für den Fedlex MCP Server.
Testet alle 7 Tools + 2 Resources mit unterschiedlichen Parametern,
Sprachen, Grenzfällen und Fehlerszenarien.
"""

import asyncio
import logging
import os
import sys
import time
import traceback

# Fix Windows console encoding
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Suppress httpx logging noise
logging.getLogger("httpx").setLevel(logging.WARNING)

# Server-Module importieren
sys.path.insert(0, ".")
from server import (
    SearchLawsInput,
    GetLawBySrInput,
    GetRecentPublicationsInput,
    GetUpcomingChangesInput,
    SearchGazetteInput,
    GetLawHistoryInput,
    SearchTreatiesInput,
    Language,
    fedlex_search_laws,
    fedlex_get_law_by_sr,
    fedlex_get_recent_publications,
    fedlex_get_upcoming_changes,
    fedlex_search_gazette,
    fedlex_get_law_history,
    fedlex_search_treaties,
    get_sr_resource,
    get_server_info,
)

PASS = 0
FAIL = 0
RESULTS = []


async def run_test(num: int, name: str, coro, checks: list[callable]):
    """Führt ein Testszenario aus und prüft Assertions."""
    global PASS, FAIL
    print(f"\n{'='*70}")
    print(f"TEST {num:02d}: {name}")
    print(f"{'='*70}")

    start = time.time()
    try:
        result = await coro
        elapsed = time.time() - start
        print(f"  Dauer: {elapsed:.2f}s")
        print(f"  Ergebnis (erste 500 Zeichen):")
        preview = str(result)[:500]
        for line in preview.split("\n"):
            print(f"    {line}")
        if len(str(result)) > 500:
            print(f"    ... ({len(str(result))} Zeichen total)")

        errors = []
        for i, check in enumerate(checks):
            try:
                check(result)
            except AssertionError as ae:
                errors.append(f"  Check {i+1}: FAILED — {ae}")

        if errors:
            FAIL += 1
            status = "FAILED"
            for e in errors:
                print(e)
        else:
            PASS += 1
            status = "PASSED"

        RESULTS.append((num, name, status, elapsed, errors))
        print(f"\n  >>> {status} ({len(checks)} checks)")

    except Exception as e:
        elapsed = time.time() - start
        FAIL += 1
        RESULTS.append((num, name, "ERROR", elapsed, [str(e)]))
        print(f"  FEHLER nach {elapsed:.2f}s: {e}")
        traceback.print_exc()


async def main():
    global PASS, FAIL

    # =================================================================
    # TEST 01: Stichwortsuche — Bundesverfassung finden
    # =================================================================
    await run_test(
        1,
        "fedlex_search_laws: Suche 'Verfassung' (DE, nur gültige)",
        fedlex_search_laws(SearchLawsInput(
            keywords="Verfassung",
            language=Language.DE,
            in_force_only=True,
            limit=10,
        )),
        [
            lambda r: assert_contains(r, "101"),       # BV hat SR 101
            lambda r: assert_contains(r, "Verfassung"),
            lambda r: assert_contains(r, "In Kraft"),
            lambda r: assert_contains(r, "fedlex.admin.ch"),
        ],
    )

    # =================================================================
    # TEST 02: Konkreter Erlass — Datenschutzgesetz (DSG) abrufen
    # =================================================================
    await run_test(
        2,
        "fedlex_get_law_by_sr: SR 235.1 (DSG) auf Deutsch",
        fedlex_get_law_by_sr(GetLawBySrInput(
            sr_number="235.1",
            language=Language.DE,
        )),
        [
            lambda r: assert_contains(r, "235.1"),
            lambda r: assert_contains(r, "Datenschutz"),
            lambda r: assert_contains(r, "DSG"),
            lambda r: assert_contains(r, "In Kraft"),
            lambda r: assert_contains(r, "Daten-URI"),
        ],
    )

    # =================================================================
    # TEST 03: Französische Sprache — Loi sur la protection des données
    # =================================================================
    await run_test(
        3,
        "fedlex_get_law_by_sr: SR 235.1 (LPD) auf Französisch",
        fedlex_get_law_by_sr(GetLawBySrInput(
            sr_number="235.1",
            language=Language.FR,
        )),
        [
            lambda r: assert_contains(r, "235.1"),
            lambda r: assert_contains(r, "protection des donn"),  # "protection des données"
            lambda r: assert_contains(r, "/fr"),
        ],
    )

    # =================================================================
    # TEST 04: Italienische Sprache — Suche 'protezione dei dati'
    # =================================================================
    await run_test(
        4,
        "fedlex_search_laws: 'protezione' auf Italienisch",
        fedlex_search_laws(SearchLawsInput(
            keywords="protezione",
            language=Language.IT,
            in_force_only=True,
            limit=5,
        )),
        [
            lambda r: assert_contains(r, "protezione"),
            lambda r: assert_contains(r, "[IT]"),
            lambda r: assert_contains(r, "Treffer"),
        ],
    )

    # =================================================================
    # TEST 05: Neueste AS-Publikationen der letzten 60 Tage
    # =================================================================
    await run_test(
        5,
        "fedlex_get_recent_publications: letzte 60 Tage (DE)",
        fedlex_get_recent_publications(GetRecentPublicationsInput(
            days=60,
            language=Language.DE,
            limit=5,
        )),
        [
            lambda r: assert_contains(r, "AS-Publikationen"),
            lambda r: assert_contains(r, "fedlex.admin.ch"),
            lambda r: assert_not_contains(r, "Fehler"),
        ],
    )

    # =================================================================
    # TEST 06: Bevorstehende Rechtsänderungen (365 Tage)
    # =================================================================
    await run_test(
        6,
        "fedlex_get_upcoming_changes: nächste 365 Tage (DE)",
        fedlex_get_upcoming_changes(GetUpcomingChangesInput(
            days_ahead=365,
            language=Language.DE,
            limit=10,
        )),
        [
            lambda r: assert_not_contains(r, "Fehler"),
            # Entweder Treffer oder "Keine bevorstehenden" — beides ok
            lambda r: assert_any(r, ["Bevorstehende Änderungen", "Keine bevorstehenden"]),
        ],
    )

    # =================================================================
    # TEST 07: Bundesblatt-Suche — Volksinitiative
    # =================================================================
    await run_test(
        7,
        "fedlex_search_gazette: 'Volksinitiative' (DE)",
        fedlex_search_gazette(SearchGazetteInput(
            keywords="Volksinitiative",
            language=Language.DE,
            limit=5,
        )),
        [
            lambda r: assert_contains(r, "BBl"),
            lambda r: assert_contains(r, "Volksinitiative"),
            lambda r: assert_contains(r, "fedlex.admin.ch"),
        ],
    )

    # =================================================================
    # TEST 08: Bundesblatt-Suche mit Jahr-Filter
    # =================================================================
    await run_test(
        8,
        "fedlex_search_gazette: 'Bildung' im Jahr 2024 (DE)",
        fedlex_search_gazette(SearchGazetteInput(
            keywords="Bildung",
            language=Language.DE,
            year=2024,
            limit=10,
        )),
        [
            lambda r: assert_contains(r, "BBl"),
            lambda r: assert_contains(r, "2024"),
            lambda r: assert_not_contains(r, "Fehler"),
        ],
    )

    # =================================================================
    # TEST 09: Versionsgeschichte — BV (SR 101)
    # =================================================================
    await run_test(
        9,
        "fedlex_get_law_history: SR 101 (Bundesverfassung)",
        fedlex_get_law_history(GetLawHistoryInput(
            sr_number="101",
            language=Language.DE,
        )),
        [
            lambda r: assert_contains(r, "Versionsgeschichte"),
            lambda r: assert_contains(r, "101"),
            lambda r: assert_contains(r, "Inkrafttreten"),
            # BV hat mehrere Fassungen
            lambda r: assert_contains(r, "v1"),
        ],
    )

    # =================================================================
    # TEST 10: Staatsverträge — Menschenrechte
    # =================================================================
    await run_test(
        10,
        "fedlex_search_treaties: 'Menschenrechte' (DE)",
        fedlex_search_treaties(SearchTreatiesInput(
            keywords="Menschenrechte",
            language=Language.DE,
            limit=5,
        )),
        [
            lambda r: assert_contains(r, "Staatsverträge"),
            lambda r: assert_contains(r, "0."),  # SR-Nummern beginnen mit 0.
            lambda r: assert_contains(r, "Menschenrecht"),
        ],
    )

    # =================================================================
    # TEST 11: Staatsverträge ohne Suchbegriff (neueste)
    # =================================================================
    await run_test(
        11,
        "fedlex_search_treaties: ohne Keywords (neueste Verträge)",
        fedlex_search_treaties(SearchTreatiesInput(
            keywords=None,
            language=Language.DE,
            limit=5,
        )),
        [
            lambda r: assert_contains(r, "Staatsverträge"),
            lambda r: assert_contains(r, "0."),
            lambda r: assert_contains(r, "Treffer"),
        ],
    )

    # =================================================================
    # TEST 12: Nicht existierende SR-Nummer — Fehlerbehandlung
    # =================================================================
    await run_test(
        12,
        "fedlex_get_law_by_sr: SR 999.999 (existiert nicht)",
        fedlex_get_law_by_sr(GetLawBySrInput(
            sr_number="999.999",
            language=Language.DE,
        )),
        [
            lambda r: assert_contains(r, "Kein Erlass"),
            lambda r: assert_contains(r, "999.999"),
            lambda r: assert_contains(r, "Mögliche Ursachen"),
        ],
    )

    # =================================================================
    # TEST 13: Suche ohne Treffer — seltener Begriff
    # =================================================================
    await run_test(
        13,
        "fedlex_search_laws: 'Quantencomputing' (kein Treffer erwartet)",
        fedlex_search_laws(SearchLawsInput(
            keywords="Quantencomputing",
            language=Language.DE,
            in_force_only=True,
            limit=5,
        )),
        [
            lambda r: assert_contains(r, "Keine Erlasse"),
            lambda r: assert_contains(r, "Tipps"),
        ],
    )

    # =================================================================
    # TEST 14: Resource fedlex://info — Server-Metadaten
    # =================================================================
    await run_test(
        14,
        "Resource fedlex://info — Server-Metadaten abrufen",
        get_server_info(),
        [
            lambda r: assert_contains(r, "Fedlex MCP Server"),
            lambda r: assert_contains(r, "1.0.0"),
            lambda r: assert_contains(r, "fedlex_search_laws"),
            lambda r: assert_contains(r, "JOLux"),
            lambda r: assert_contains(r, '"rm"'),
        ],
    )

    # =================================================================
    # TEST 15: Resource fedlex://sr/{sr_number} — BV abrufen
    # =================================================================
    await run_test(
        15,
        "Resource fedlex://sr/101 — Bundesverfassung via Resource",
        get_sr_resource("101"),
        [
            lambda r: assert_contains(r, "101"),
            lambda r: assert_contains(r, "Bundesverfassung"),
            lambda r: assert_contains(r, "In Kraft"),
            lambda r: assert_contains(r, "/de"),  # Default-Sprache ist DE
        ],
    )

    # =================================================================
    # ZUSAMMENFASSUNG
    # =================================================================
    print(f"\n{'='*70}")
    print(f"ZUSAMMENFASSUNG — 15 Testszenarien")
    print(f"{'='*70}")
    print(f"  BESTANDEN: {PASS}")
    print(f"  FEHLGESCHLAGEN: {FAIL}")
    print(f"  TOTAL: {PASS + FAIL}")
    print()

    print(f"{'Nr':>3} | {'Status':<8} | {'Dauer':>6} | Szenario")
    print(f"{'-'*3}-+-{'-'*8}-+-{'-'*6}-+-{'-'*45}")
    for num, name, status, elapsed, errors in RESULTS:
        icon = "OK" if status == "PASSED" else "XX"
        print(f" {num:02d} | {icon:<8} | {elapsed:5.2f}s | {name}")
        for err in errors:
            print(f"    |          |        | {err}")

    print(f"\n{'='*70}")
    if FAIL == 0:
        print("ALLE TESTS BESTANDEN!")
    else:
        print(f"{FAIL} TEST(S) FEHLGESCHLAGEN!")
    print(f"{'='*70}")

    return FAIL == 0


# ---- Hilfsfunktionen für Assertions ----

def assert_contains(result: str, substring: str):
    assert substring in str(result), f"Erwartet '{substring}' im Ergebnis"


def assert_not_contains(result: str, substring: str):
    assert substring not in str(result), f"Unerwartetes '{substring}' im Ergebnis"


def assert_any(result: str, options: list[str]):
    r = str(result)
    assert any(opt in r for opt in options), f"Keines von {options} im Ergebnis"


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
