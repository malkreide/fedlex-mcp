"""Zugriff auf die aufgezeichneten Fixtures unter ``tests/fixtures/``.

Herkunft, Datum, Auswahlregel und SHA-256 stehen je Datei in
``tests/fixtures/PROVENANCE.md``, geschrieben von ``scripts/record_fixtures.py``.

Die Dateien belegen die *Form* der Antwort und einen datierten Ausschnitt ihres
Inhalts. Zusicherungen leiten ihre Erwartungen deshalb aus der Fixture ab,
statt Zahlen hineinzuschreiben — eine feste Zeilenzahl waere beim naechsten
Aufzeichnen falsch, ohne dass sich etwas Geprueftes geaendert haette.

Ein fehlender Name ist ein Fehler und keine leere Struktur: Der Rueckfallwert
eines Lookups waere sonst die ganze Ursache.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _pfad(name: str) -> Path:
    path = FIXTURES / name
    if not path.is_file():
        available = sorted(p.name for p in FIXTURES.iterdir() if p.is_file())
        raise FileNotFoundError(
            f"Keine Fixture {name!r} unter {FIXTURES}. Vorhanden: {available}. "
            "Neu aufzeichnen mit `python scripts/record_fixtures.py`."
        )
    return path


def fixture_bytes(name: str) -> bytes:
    return _pfad(name).read_bytes()


def fixture_text(name: str) -> str:
    return _pfad(name).read_bytes().decode("utf-8", errors="replace")


def fixture_json(name: str) -> Any:
    return json.loads(fixture_text(name))


def provenance() -> str:
    return fixture_text("PROVENANCE.md")


def recorded_names() -> list[str]:
    """Alle aufgezeichneten Antwortdateien, ohne PROVENANCE.md."""
    return sorted(p.name for p in FIXTURES.iterdir() if p.name != "PROVENANCE.md")
