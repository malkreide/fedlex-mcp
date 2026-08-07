# Mitwirken an fedlex-mcp

[:gb: English Version](CONTRIBUTING.md)

Vielen Dank für Ihr Interesse an einem Beitrag! Dieser Server ist Teil des [Swiss Public Data MCP Portfolios](https://github.com/malkreide).

---

## Probleme melden

Nutzen Sie [GitHub Issues](https://github.com/malkreide/fedlex-mcp/issues), um Fehler zu melden oder Funktionen vorzuschlagen.

Bitte geben Sie an:
- Python-Version und Betriebssystem
- Vollständige Fehlermeldung oder Beschreibung des unerwarteten Verhaltens
- Schritte zur Reproduktion

---

## Pull Requests

1. Forken Sie das Repository
2. Erstellen Sie einen Feature-Branch: `git checkout -b feat/ihr-feature`
3. Nehmen Sie Ihre Änderungen vor und ergänzen Sie Tests
4. Stellen Sie sicher, dass alle Tests bestehen: `PYTHONPATH=src pytest tests/ -m "not live"`
5. Committen Sie nach [Conventional Commits](https://www.conventionalcommits.org/): `feat: neues Tool hinzufügen`
6. Pushen Sie und öffnen Sie einen Pull Request gegen `main`

---

## Code-Stil

- Python 3.11+
- [Ruff](https://github.com/astral-sh/ruff) für Linting und Formatierung
- Type Hints für alle öffentlichen Funktionen erforderlich
- Tests für neue Tools erforderlich (`tests/test_server.py`)
- Den bestehenden FastMCP-/Pydantic-v2-Mustern in `server.py` folgen

---

## Datenquelle

Dieser Server nutzt den öffentlichen Fedlex-SPARQL-Endpoint — keine Authentifizierung erforderlich.

| Quelle | Dokumentation |
|--------|--------------|
| Fedlex SPARQL | [fedlex.data.admin.ch](https://fedlex.data.admin.ch/) |
| JOLux-Ontologie | [Fedlex-Datenmodell](https://fedlex.data.admin.ch/) |

Wenn Sie neue SPARQL-Abfragen hinzufügen, prüfen Sie diese zuerst manuell gegen den Endpoint und behandeln Sie Randfälle (fehlende optionale Felder, Timeout bei breiten Abfragen).

---

## Lizenz

Mit Ihrem Beitrag erklären Sie sich damit einverstanden, dass Ihre Beiträge unter der [MIT-Lizenz](LICENSE) lizenziert werden.

## Die Live-Suite: wann sie läuft, und wer ein rotes Ergebnis sieht

**Kadenz:** montags 05:43 UTC, dazu jederzeit von Hand über *Actions → Live-Tests → Run
workflow*. Siehe [`.github/workflows/live-tests.yml`](.github/workflows/live-tests.yml).

**Wer es sieht:** Ein roter Lauf öffnet ein Issue mit dem Titel `Live-Tests gegen
fedlex.data.admin.ch rot …` und dem Label `upstream` — und kommentiert das bestehende, statt
ein zweites aufzumachen. Wird die Suite wieder grün, wird es geschlossen.

**Drei Antworten, nicht zwei.** `scripts/classify_live_run.py` liest das
JUnit-XML statt des Exit-Codes und unterscheidet: `clear` (gelaufen, grün),
`finding` (gelaufen, etwas gefallen) und `unknown` (nicht gelaufen — Installation
gescheitert, null Tests eingesammelt, alle übersprungen). Ein `unknown` schliesst
nie ein Issue: Zuzumachen hiesse zu behaupten, der Vergleich sei gelaufen.

**Ein roter Live-Lauf heisst nicht zwingend «unser Fehler».** Er heisst: Der
Vertrag mit der Quelle hat sich geändert, oder die Quelle ist gerade aus. Beides
gehört gesehen, nur das Erste gehört gefixt. Bitte den Lauf lesen, bevor der Job
deaktiviert wird — so stirbt dieser Check, und er ist der einzige im Repo, der
einer falschen Grundannahme über fedlex.data.admin.ch widersprechen kann. Jeder andere Test
prüft gegen eine Fixture, und die Fixture ist aus derselben Annahme geschrieben
wie der Code.

Das ist nicht hypothetisch: Bei `meteoswiss-mcp` fielen am 30.7.2026 beim ersten
Lauf der Live-Suite seit Monaten drei von sechs Tests — der Endpunkt war zwei
Tage zuvor abgeschafft worden, und niemand hatte die Suite gestartet.

Der PR-Lauf bleibt bei `-m "not live"`: Ein fremder 503 darf keinen fremden Pull
Request rot machen.
