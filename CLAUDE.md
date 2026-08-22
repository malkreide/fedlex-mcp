# CLAUDE.md

## Teil 1 — Portfolio-Konventionen

### Vor der Arbeit

Klon-Aktualität prüfen — Standard-Branch ermitteln, nicht `main` annehmen:

```bash
B=$(git ls-remote --symref origin HEAD | sed -n 's|^ref: refs/heads/\([^[:space:]]*\).*|\1|p')
git fetch origin "${B:?Standard-Branch nicht ermittelbar}" &&
  git rev-list --count HEAD..FETCH_HEAD
```

Drei Server im Portfolio heissen ihren Standard-Branch `master`
(`openlex-mcp`, `swiss-courts-mcp`, `swisstopo-mcp`); dort scheitert ein fest
verdrahtetes `origin/main` mit «couldn't find remote ref main». Wer das für ein
Netzproblem hält, arbeitet weiter auf genau dem veralteten Klon, vor dem dieser
Absatz warnt. Den `:?`-Schutz nicht weglassen: Bei leerem `B` fetcht git still
den Remote-HEAD und endet mit 0.

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

### Wenn Codex gar nicht erst hinsieht

Die Zeile oben unterstellt, dass es einen Befund geben *kann*. Das ist nicht
immer so, und man sieht es dem PR nicht an.

Am 21.8.2026 war das Code-Review-Kontingent zwischen 08:41 und 09:48
aufgebraucht — davor echte Reviews, danach in 30 Repos nur noch:

```
You have reached your Codex usage limits for code reviews.
```

Bis mindestens zum 22.8. um 08:30, also 23 Stunden später, blieb es dabei. In
der Zwischenzeit sind 32 PRs mit formal erfülltem Häkchen gemergt worden, ohne
dass jemand hineingesehen hat.

Drei Gründe, warum Codex schweigt, und nur einer davon ist harmlos:

- **Kein Befund** — dann reagiert er mit 👍 und schreibt nichts.
- **Der PR ist ein Draft** — darauf läuft Codex nicht an.
- **Das Kontingent ist weg** — dann schreibt er die Meldung oben.

«Kein Kommentar» heisst also nicht «geprüft und sauber». Unterscheiden lässt es
sich an der Form: Ein echter Review ist ein Review-Objekt («💡 Codex Review»,
mit Commit-Angabe), die Limit-Meldung ein gewöhnlicher Issue-Kommentar. Das
sind zwei verschiedene Abfragen — `get_reviews` gegen `get_comments`; wer nur
eine davon nimmt, übersieht die andere Hälfte. Genau so ist die Limit-Meldung
zuerst durchgerutscht.

Portfolio-weit nachsehen:

```
search_pull_requests: user:malkreide commenter:chatgpt-codex-connector[bot] updated:>=<Datum>
```

Findet nur, wo er *kommentiert* hat. Repos ohne PR-Aktivität tauchen nicht auf
— das ist kein Beleg, dass dort geprüft wurde.

Zweiter Weg, den Prüfer zu verlieren, ganz ohne Kontingentproblem: zu schnell
mergen. Am 21./22.8. lagen zwischen «ready for review» und Merge mehrfach drei
bis fünf Sekunden. Codex wird beim Umschalten von Draft auf ready ausgelöst und
braucht danach Zeit; wer sofort mergt, hat das Häkchen gesetzt und den Review
nicht abgewartet.

Das Kontingent hängt am Konto, nicht am Repo, und Code-Reviews haben einen
eigenen Topf — nur GitHub-getriggerte Reviews zählen hinein. ChatGPT-Pläne
fahren ein rollendes Fünf-Stunden-Fenster plus Wochenlimits; welches greift,
steht im Codex-Dashboard. Zeigt das freies Kontingent, während Reviews weiter
scheitern, ist das ein bekannter Fehler bei mehreren verbundenen Konten — dann
den GitHub-Connector in den Codex-Einstellungen trennen und neu verbinden.

### Wenn zwei Agenten dasselbe tun

Vor dem Anlegen eines Branches mit vorgegebenem Namen prüfen, ob es ihn schon
gibt:

```bash
git ls-remote --heads origin claude/<name> | wc -l
```

Steht dort `1`, arbeitet jemand anderes daran — mit Schreibrecht auf denselben
Ref.

Ein PR mit leerem Diff wird geschlossen, nicht gemergt. Der Test ist
`get_files` auf dem PR: kommt `[]` zurück, ändert er nichts. Ein grüner Check
sagt dazu nichts — die CI prüft den Head, nicht die Differenz zur Basis.

Am 21.8.2026 liefen zwei Sessions dieselbe Aufgabe über 45 Repos, auf den
Branches `claude/codex-review-audit-templates-9sn6mx` und
`claude/codex-review-audit-7ioh56`. Wo die eine zuerst nach `main` kam, wurde
`main` in den Branch der anderen gemergt und der add/add-Konflikt zugunsten
von `main` aufgelöst. Übrig blieben 14 PRs, die durch sämtliche Gates grün
liefen und nichts enthielten; sie wurden gemergt und hinterliessen leere
Merge-Commits. Mit den zwei Folge-PRs, die aus demselben Grund gegenstandslos
waren, waren 16 der 59 PRs jenes Tages reine Reibung.

Dieselbe Klasse wie der handgeschriebene Stub, der denselben Feldnamen annahm
wie der Code: Nichts ist rot, weil nichts geprüft wird, worauf es ankommt.

## Teil 2 — Dieses Repo (fedlex-mcp)

### ruff: 0.16.3, eine Stelle

`pyproject.toml` `[dev]` pinnt exakt `ruff==0.16.3`, und nur dort.
`pip install -e ".[dev]"` liefert damit lokal dieselbe Version, die die CI
fährt — die Gates sind ohne Zusatzschritt reproduzierbar.

`ci.yml` hatte zusätzlich ein `pip install ruff==0.16.1` nach dem Install. Die
Zahlen stimmten überein, aber die Konstruktion konnte das nicht sicherstellen:
Der zweite Schritt überschrieb den ersten, also wäre ein `>=` im `dev`-Extra
in der CI nie aufgefallen und hätte nur lokal wehgetan. Ein dritter Ort für
dieselbe Version wäre ein dritter Ort zum Vergessen — eine
`.pre-commit-config.yaml` gibt es bewusst nicht.

Vor dem Lauf `ruff --version` prüfen: ein älteres ruff früher im `PATH`
schlägt den Pin, ohne dass der Install etwas meldet.

### Gate-Befehle, wörtlich aus `ci.yml`

```
pip install -e ".[dev]"
PYTHONPATH=src pytest tests/ -m "not live"
python scripts/check_ruff_pin.py
ruff check src/ tests/ scripts/
ruff format --check src/ tests/ scripts/
```

Matrix: Python 3.11, 3.12, 3.13. Zusätzlich `security.yml`: gitleaks-Secret-Scan.
Alle Gates laufen auf allen drei Versionen, keine `if:`-Ausnahme; ein
`fail-fast: false` steht nicht da.

**Der SEC-022-Schutz steht nicht in dieser Liste, und das ist Absicht.** Er
liegt in `tests/test_server.py::test_tool_definitions_match_lock`, läuft also
im `pytest` mit und vergleicht die Tool-Definitionen gegen
`tool-definitions.lock.json`. Die Schwester-Server fahren dafür einen eigenen
CI-Schritt (`--check`); wer die Gate-Liste hier danach absucht, findet nichts
und schliesst falsch, der Schutz fehle. Nach einer beabsichtigten Änderung
`PYTHONPATH=src python scripts/snapshot_tools.py` und die Lock-Datei
mitcommitten.

**Es gibt kein Versions-Sync-Gate.** `scripts/` enthält
`classify_live_run.py`, `record_fixtures.py` und `snapshot_tools.py` — kein
`check_version_sync.py`, und kein Workflow ruft eines auf. `pyproject.toml`
und `server.json` stehen beide auf `2.0.1`, gehalten wird das von nichts.
Beim Anheben also beide Stellen von Hand.

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
