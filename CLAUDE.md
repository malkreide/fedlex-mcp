# CLAUDE.md

## Teil 1 — Portfolio-Konventionen

### Vor der Arbeit

Klon-Aktualität prüfen: `git fetch origin main && git rev-list --count HEAD..origin/main`
Ein veralteter Klon erzeugt eine rote CI, deren Ursache nicht im Diff steht.
Am 3.8.2026 zweimal passiert — beide Male fehlten genau die Commits, die
das Gate einführten, an dem der Branch scheiterte.

Gates lokal fahren, mit der GEPINNTEN ruff-Version aus der CI. Eine andere
Version meldet Abweichungen, die niemand verursacht hat.

### Tests

Gegenprobe ist Pflicht. Ein Test, der grün bleibt, wenn man die
Implementierung entfernt, prüft nichts. Jede neue Zusicherung einzeln
neutralisieren und zeigen, dass genau die zugehörigen Tests fallen.

Zwei Fallen, die beide grün blieben:

- Eine Fake-Uhr, die nur beim Schlafen vorrückt, kann eine Zusicherung über
  echte Zeit nicht widerlegen.
- `monkeypatch.setattr(modul.asyncio, "sleep", ...)` greift ins Modul
  `asyncio` selbst und entschärft die Mechanik im ganzen Prozess. Patche
  einen Modul-Alias (`_sleep = asyncio.sleep`), nicht das fremde Modul.

Handgeschriebene Fixtures kodieren die Annahme des Autors und können sie
nicht widerlegen. Mindestens eine aufgezeichnete Antwort pro externem
Endpunkt, mit Aufnahmedatum.

### Wenn etwas rot ist

Roter Live-Test: erst die Quelle abfragen, dann einordnen. Nicht aus der
Fehlermeldung schliessen. Am 3.8.2026 hiess "nicht gefunden" nicht, dass der
Datensatz weg war, sondern dass die Quelle die Schreibweise ihrer Kopfzeile
gewechselt hatte — vier von sechs Datensätzen produktiv kaputt, alle
Unit-Tests grün.

PR ohne jeden Check ist selten ein Repo ohne CI, meistens ein
Merge-Konflikt: GitHub berechnet dafür keinen Merge-Commit und startet nichts.

Ein Codex-Review auf einem PR wird beantwortet oder behoben, nie ignoriert.

## Teil 2 — Dieses Repo (fedlex-mcp)

### ruff: 0.16.1, eine Stelle

`pyproject.toml` `[dev]` pinnt exakt `ruff==0.16.1`, und nur dort.
`pip install -e ".[dev]"` liefert damit lokal dieselbe Version, die die CI
fährt — die Gates sind ohne Zusatzschritt reproduzierbar.

`ci.yml` hatte zusätzlich ein `pip install ruff==0.16.1` nach dem Install. Die
Zahlen stimmten überein, aber die Konstruktion konnte das nicht sicherstellen:
Der zweite Schritt überschrieb den ersten, also wäre ein `>=` im `dev`-Extra
in der CI nie aufgefallen und hätte nur lokal wehgetan. Ein dritter Ort für
dieselbe Version wäre ein dritter Ort zum Vergessen — eine
`.pre-commit-config.yaml` gibt es bewusst nicht.

### Gate-Befehle, wörtlich aus `ci.yml`

```
pip install -e ".[dev]"
PYTHONPATH=src pytest tests/ -m "not live"
ruff check src/ tests/ scripts/
ruff format --check src/ tests/ scripts/
```

Matrix: Python 3.11, 3.12, 3.13. Zusätzlich `security.yml`: gitleaks-Secret-Scan.

CI-Status über die Checks-API lesen (`actions_list`, `list_workflow_runs`).
Die Commit-Status-API (`get_status`) meldet hier immer `total_count: 0` — das
Repo fährt reine Actions, und die melden nicht dorthin. Wer diese Null als
«keine CI gelaufen» liest, erklärt einen grünen Lauf zum Ausfall.

### Live-Tests: geplanter Workflow vorhanden

`.github/workflows/live-tests.yml`, `cron: "43 5 * * 1"` (wöchentlich Mo,
05:43 UTC) plus `workflow_dispatch`. Die Live-Suite ist also nicht bloss per
`-m "not live"` ausgeschlossen — DRIFT-005 ist hier erfüllt.

Der Lauf hat drei Ausgänge (`clear` / `finding` / `unknown`), eingeordnet aus
dem JUnit-XML von `scripts/classify_live_run.py`, nicht aus dem Exit-Code.
Wer an der Live-Suite oder am Workflow arbeitet: die Begründung steht im
Kopfkommentar von `live-tests.yml`, die Einordnung ist über
`tests/test_classify_live_run.py` getestet.
