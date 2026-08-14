# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **Der Backoff-Schlaf wird ueber einen Modul-Alias gepatcht, nicht ueber
  `asyncio.sleep`.** Die Tests nullten die Wartezeit mit
  `monkeypatch.setattr(<modul>.asyncio, "sleep", ...)`. Das liest sich lokal,
  ersetzt `sleep` aber auf dem geteilten Modulobjekt — fuer httpx, respx,
  pytest-asyncio und jeden anderen Importeur im Prozess. Das Modul legt die
  Naht jetzt als `_sleep = asyncio.sleep` offen; gepatcht wird diese.
  `test_der_retry_geht_ueber_den_alias` haelt sie: umgeht der Retry den Alias,
  faellt der Test in Sekundenbruchteilen. Ohne ihn fiel gar nichts — die Suite
  wurde nur ein Vielfaches langsamer, und eine laengere Laufzeit ist kein
  Signal, das jemand liest.

### Hinzugefuegt — die Live-Suite laeuft geplant, statt nur markiert zu sein

`ci.yml` faehrt `pytest tests/ -m "not live"`. Das ist richtig — ein fremder 503
darf keinen fremden Pull Request rot machen — und es liess die Live-Tests seit
ihrer Entstehung an keiner Stelle laufen. **`-m "not live"` ist kein Ort, an dem
Tests laufen; es ist die Abwesenheit eines solchen.**

Ausgerechnet sie sind die einzigen im Repo, die einer falschen Grundannahme
ueber fedlex.data.admin.ch widersprechen koennen: Jeder andere Test prueft gegen eine
Fixture, und die Fixture ist aus derselben Annahme geschrieben wie der Code. Bei
`meteoswiss-mcp` fielen am 30.7.2026 beim ersten Lauf seit Monaten drei von sechs
Tests; bei `zh-education-mcp` lief am 3.8.2026 der Code monatelang gegen
umbenannte Feldnamen, ohne dass ein Test rot wurde.

`.github/workflows/live-tests.yml`: montags 05:43 UTC auf einer ungeraden Minute, dazu
`workflow_dispatch`. Der PR-Lauf bleibt unveraendert — dies ist ein
*zusaetzlicher* Lauf, kein Umbau.

**Drei Antworten, nicht zwei.** `if: failure()` kennt rot und nicht rot; ein
gescheitertes `pip install` saehe damit aus wie ein gebrochener Vertrag mit der
Quelle. `scripts/classify_live_run.py` liest deshalb das JUnit-XML und trennt
`clear`, `finding` und `unknown`. Ein `unknown` schliesst nie ein Issue:
zuzumachen hiesse zu behaupten, der Vergleich sei gelaufen.

Der Fall, der die Einordnung noetig macht, ist der uebersprungene Lauf: pytest
endet mit 0, wenn jeder Test uebersprungen wurde. `tests - skipped == 0` ist
deshalb `unknown` — gemessen am 7.8.2026 an `swiss-transport-mcp`, wo ohne
`TRANSPORT_API_KEY` alle sechs Live-Tests uebersprungen werden und ein
Exit-Code-Check gruen gemeldet haette.

Die Einordnung steht in einem Skript mit eigenem Test, nicht in einem
`run:`-Block: Sie entscheidet, ob ein Issue auf- oder zugeht, und das ist der
einzige Teil des Workflows, der etwas behauptet.

Ein Issue mit stabilem Titel-Praefix und Label `upstream` wird kommentiert statt
verdoppelt. Die pytest-Ausgabe geht ueber `env` ins Skript, nicht ueber `${ }`
— sie ist fremder Text, der sonst in einem JavaScript-Template-Literal landet.

Kadenz und Zustaendigkeit stehen in CONTRIBUTING (beide Sprachen). Gemessen mit
`live_schedule_probe` aus `mcp-continuous-auditor`: vorher `LIVE_UNSCHEDULED`,
jetzt `LIVE_SCHEDULED`.

### Behoben

- **Der 20-Sekunden-Deckel war keine Grenze.** Gedeckelt wurde *vor* dem
  Jittern, also wurde ein auf `MAX_DELAY_S` gedeckelter Wert anschliessend mit
  bis zu 1.5 multipliziert: exponentielle Wartezeiten bis 30 s,
  `Retry-After`-Wartezeiten bis 25 s. Die Konstante behauptete eine Schranke,
  die sie nicht einhielt. Neu wird nach dem Jittern gedeckelt.

- **Das Gesamtbudget war nicht garantiert.** `httpx` wendet sein Timeout pro
  Operation an (connect/read/write/pool), und das Read-Timeout beginnt mit jedem
  Chunk von vorn — eine langsam troepfelnde Antwort konnte das Budget
  ueberdauern, ohne dass ein einzelner Read ablief. Neu liegt eine
  `asyncio.timeout`-Deadline um den Request; das httpx-Timeout bleibt als
  feinere Grenze pro Operation daneben. Weil `_request_with_retry` der
  gemeinsame Kern ist, gilt beides fuer SPARQL- und JSON-Requests zugleich.

  Beide Befunde stammen aus einem Codex-Review an `parlament-mcp#35`, wo
  dasselbe Muster nach der Uebernahme geprueft wurde. Der Test dazu laeuft
  bewusst **ohne** die Fake-Uhr der uebrigen Budget-Tests: Die Zusicherung
  haengt an echter Zeit, und eine Uhr, die nur beim Schlafen vorrueckt, kann sie
  nicht widerlegen — genau dieser blinde Fleck liess den Fehler durch.

### Added

- **Retry-Politik gegenueber den SPARQL-Endpoints** (ARCH-014), im gemeinsamen
  Retry-Kern und damit fuer SPARQL- und JSON-Requests zugleich.

  `Retry-After` bei 429 und 503 in beiden Formen (Sekundenzahl und HTTP-Datum,
  RFC 9110 §10.2.3) schlaegt die eigene Backoff-Kurve. Ein unbrauchbarer Header
  fuehrt zurueck auf die Kurve statt zum Absturz.

  Jitter: `base_delay * 2**attempt` war deterministisch, alle Clients retryen im
  Gleichtakt und die Last kommt als Welle zurueck, genau wenn der Endpoint sich
  erholt. Neu [0.5x, 1.5x]; auf einem `Retry-After` einseitig [1.0x, 1.25x].
  Deckel von 20 s auf jede Einzelwartezeit.

  Gesamtbudget von 45 s ueber den ganzen Aufruf. Der Wert liegt **bewusst ueber**
  dem MCP-Client-Default (`MCP_DEFAULT_TIMEOUT = 30.0`), aus demselben Grund, aus
  dem `REQUEST_TIMEOUT` und `LINDAS_TIMEOUT` bei 45 s stehen: Beides sind
  SPARQL-Endpoints, und ein Budget unter 30 s wuerde legitime Queries abwuergen.
  Ein Test haelt die Abweichung fest.


## [2.0.1] - 2026-08-02

### Behoben

- **`structlog` hatte keine Obergrenze, und der Index fuehrt bereits einen Major
  oberhalb der Untergrenze.** Deklariert war `structlog>=25.5.0`; auf PyPI liegt
  `26.1.0`. Das Artefakt aendert sich nicht — die Antwort des Resolvers auf
  die naechste frische Installation schon, und genau so wurde
  `swiss-energy-mcp` 0.3.3 uninstallierbar, als `mcp` 2.0.0 das Modul entfernt
  hat, das es importierte.

  Neu `structlog>=25.5.0,<27`. Die Grenze ist gemessen, nicht geraten: dieses Paket installiert
  und importiert heute gegen `structlog 26.1.0`, die Obergrenze laesst also zu,
  was nachweislich funktioniert, und stoppt nur den naechsten, unbekannten
  Major.

Ein Abhaengigkeitsbereich erreicht die Nutzenden nur ueber ein neues
Release, daher der Versions-Bump. Am Code aendert sich nichts.

## [2.0.0] - 2026-08-01

> **Sammelrelease.** Diese Version liefert alles aus, was seit 1.0.3 auf `main`
> aufgelaufen ist — 22 Commits, darunter die beiden Stände, die bis zum
> 01.08.2026 fälschlich als `[1.1.0]` und `[1.2.0]` in diesem CHANGELOG standen,
> obwohl keiner von beiden je ausgeliefert wurde: kein Tag, kein PyPI-Upload,
> kein GitHub-Release. Ihr Inhalt ist unverändert übernommen und unten als
> eigene Blöcke erhalten, damit nachvollziehbar bleibt, was wann entstanden ist.
>
> **Warum 2.0.0 und nicht das vorbereitete 1.2.0:** die Migration auf das
> `mcp`-SDK 2.x hebt die Abhängigkeit von `<2` auf `>=2.0.0,<3`. In einer
> Umgebung, die `mcp` auf 1.x festhält, bricht die Installation — ein Breaking
> Change, den auch der Commit selbst so markiert (`feat!`). Der MCP-Tool-Vertrag
> ist davon nicht betroffen: 12 Tools, 2 Resources, `tool-definitions.lock.json`
> unverändert. Wer den Server wie dokumentiert über `uvx` startet, merkt vom
> Major-Sprung nichts.

### Fixed

- **Streamable-HTTP wies unter jedem echten Hostnamen mit 421 ab (SEC-005).**
  `_run_http()` baute die App mit `mcp.streamable_http_app()` ohne `host` — und
  zwar **bevor** Host und Port überhaupt aufgelöst waren. Der Bind konnte also
  gar nicht ankommen. Unter mcp 2.x ist das kein neutraler Default: das SDK
  leitet aus dem App-Argument seine Host-Allow-List ab und aktiviert bei
  loopback-artigem Wert automatisch `127.0.0.1:*`. Da der Default `127.0.0.1`
  ist, traf das jeden Start mit `FEDLEX_HOST=0.0.0.0`.

  Der Bind wird jetzt zuerst ermittelt (`resolve_http_bind()`) und dann an beide
  Abnehmer gegeben — uvicorn und die App. Eine echte Allow-List entsteht aus dem
  neuen `FEDLEX_ALLOWED_HOSTS`; ohne diese Variable bleibt der Schutz auf einem
  Nicht-Loopback-Bind bewusst aus und der Aufrufer warnt.

  13 neue Tests, darunter der tragende Fall „richtiger Hostname, falscher Port"
  und einer, der die Bind-Auflösung festnagelt (`PORT` schlägt `--port`, `--port`
  schlägt die Settings) — sonst könnte die App später wieder einen anderen Wert
  sehen als uvicorn. Mutationsgetestet: nimmt man den `host`-Kwarg wieder weg,
  reproduziert der Test das 421.

  Geprüft mit den wörtlichen CI-Kommandos: 94 passed / 3 deselected,
  `ruff check src/ tests/` clean.


### Geändert — Breaking

- **Migration auf das `mcp`-Python-SDK 2.x.** Der Server importiert nicht mehr
  `mcp.server.fastmcp`, sondern `mcp.server.mcpserver`; aus `FastMCP` wird
  `MCPServer`. Die Abhängigkeit lautet damit `mcp[cli]>=2.0.0,<3` statt
  `>=1.28.1,<2` — das ist der Breaking-Anteil: wer `fedlex-mcp` in eine Umgebung
  installiert, die `mcp` auf 1.x festhält, bekommt jetzt einen
  Auflösungskonflikt. Unter `uvx`, dem dokumentierten Installationsweg, ist die
  Umgebung isoliert und die Änderung unsichtbar.

  **Der Tool-Vertrag bleibt bewusst unverändert.** `mcp_types` 2.x hat die
  Python-Felder auf snake_case umbenannt (`inputSchema` → `input_schema`,
  `outputSchema` → `output_schema`); `compute_tool_signature_hash()` liest jetzt
  die neuen Namen und dumpt die Annotations mit `by_alias=True`, damit die
  Draht-Schreibweise (`readOnlyHint`, …) erhalten bleibt. Ohne dieses `by_alias`
  hätte sich der Signatur-Hash geändert, ohne dass sich am Vertrag etwas ändert —
  die Drift-Erkennung aus SEC-022 hätte falsch angeschlagen.
  `tool-definitions.lock.json` ist entsprechend unverändert geblieben; die 12
  Tools und 2 Resources sind identisch.

  Protokollseitig bringt 2.x eine neuere Revision mit
  (`LATEST_PROTOCOL_VERSION` = `2026-07-28`). Sie wird beim `initialize`-Handshake
  ausgehandelt, ältere Clients bleiben also bedient.

### Behoben

- **`mcp` auf `<2` begrenzt.** `mcp` 2.0.0, veröffentlicht am 28.07.2026, hat
  `mcp.server.fastmcp` entfernt — genau das Modul, das dieser Server importiert.
  Mit dem bisherigen offenen `>=1.28.1` wählte jede frische Auflösung 2.0.0 und
  scheiterte beim Import mit `ModuleNotFoundError`, in der CI ebenso wie bei
  jedem `pip install`. In beide Richtungen verifiziert: 2.0.0 scheitert, `<2`
  löst auf 1.29.0 auf und importiert sauber. Die Migration auf die 2.x-API
  (`mcp.server.mcpserver`) bleibt eine eigene, bewusste Aufgabe.

  > **Zwischenstand, inzwischen überholt.** Die Migration ist im selben
  > Release-Zyklus erfolgt (siehe «Geändert — Breaking»). Ausgeliefert wird
  > `mcp[cli]>=2.0.0,<3`, **nicht** `<2`. Der Eintrag bleibt stehen, weil er
  > erklärt, warum diese Abhängigkeit überhaupt eine Obergrenze trägt.

- **`mcp`-Untergrenze auf `>=1.28.1` angehoben (CVE-2026-59950).** Vorher stand
  dort ein offenes `>=1.3.0`, unter dem eine frische Auflösung eine verwundbare
  SDK-Version hätte wählen können. Die heute ausgelieferte Untergrenze
  (`>=2.0.0`) schliesst den betroffenen Bereich weiterhin aus.

### Hinzugefügt — Verteilung und Installation

- **`server.json`** ergänzt: Registry-Metadaten für die MCP Registry
  (`io.github.malkreide/fedlex-mcp`, `registryType: pypi`, `runtimeHint: uvx`,
  Kategorie «Legal, Courts & Regulatory»). Bis dahin existierte die Datei nicht,
  obwohl der `mcp-name`-Marker im README seit 1.0.3 auf sie vorbereitet war.
- **`## Installation` im README** mit dem `uvx`-Client-Snippet für die
  `mcpServers`-Konfiguration (Claude Desktop, Cursor, Windsurf; Hinweis auf den
  Top-Level-Schlüssel `servers` für VS Code). Der generierte Block war ans
  Dateiende gehängt worden — hinter `## Author` und `## Credits`, und als
  **zweite** `## Installation`-Überschrift. Er steht jetzt an der richtigen
  Stelle (nach `## Prerequisites`), die Marker `BEGIN/END GENERATED: install`
  sind erhalten, und der bisherige Abschnitt heisst zur Unterscheidung
  `## Installation from source`. Damit löst der Anker `#installation` wieder auf
  den empfohlenen Weg auf und die Schluss-Sektionen stehen wieder am Schluss.
- **Publish in die MCP Registry** als eigener Workflow-Job (`publish-mcp`),
  nachgelagert zum PyPI-Upload, authentifiziert über GitHub-OIDC
  (`mcp-publisher login github-oidc`). Der Job zieht `version` und
  `packages[0].version` in `server.json` aus dem Release-Tag nach, damit
  Tag, Paket und Registry-Eintrag nicht auseinanderlaufen können.

### Geändert — Dokumentation und Interna

- README (beide Sprachfassungen): Schluss-Sektionen in der Reihenfolge
  Contributing → Security statt Security → Contributing.
- README (EN): Die Sektion «MCP Protocol Version» nannte die SDK-Grenze
  `>=1.3.0` und war damit über drei Abhängigkeitsänderungen hinweg falsch; sie
  verweist jetzt auf `pyproject.toml` statt eine Version zu wiederholen.
- `ruff` in `pyproject.toml` mit Obergrenze gepinnt (`>=0.15.15,<0.17`). Ohne
  Obergrenze installiert die CI die jeweils neuste Version; ein geänderter
  Default-Regelsatz färbt den Lauf dann rot, ohne dass sich eine Zeile Code
  geändert hat.
- `actions/checkout` in `ci.yml`, `publish.yml` und `security.yml` von v6 auf v7
  angehoben (Dependabot).

### Aus der nie ausgelieferten 1.2.0 (dokumentiert am 20.07.2026)

Vertieft die Vernehmlassungs-Schicht auf ein fristenzentriertes Produkt: die
Restfrist wird zur Kernaussage. Keine neuen Tools (bleibt bei 12); die drei
bestehenden `fedlex_*consultation*`-Tools werden gehärtet. Vollständig
rückwärtskompatibel für SR/AS/BBl/TERMDAT.

#### Added
- **`days_remaining` in jeder Vernehmlassungs-Antwort**, zur Laufzeit berechnet
  (nie gecacht, nie geschätzt) gegen **Europe/Zurich**. Kalendertag-Semantik:
  `0` = Frist endet heute, negativ = abgelaufen. Zentral in einer testbaren
  Funktion (`consultations.days_until` / `deadline_status`).
- **Abgeleiteter `status` — die Frist gewinnt.** Sagt die Quelle «Laufend», die
  Frist liegt aber in der Vergangenheit, wird der Status `Abgeschlossen`; das
  rohe Quell-Label bleibt als `status_source` sichtbar, der Widerspruch als
  `status_conflict: true`. Eine abgelaufene Vernehmlassung erscheint nie als
  laufend.
- **Typisiertes `Consultation`-Pydantic-v2-Modell** mit den Pflichtfeldern
  `title, status, opened_on, deadline, days_remaining, lead_office, source_url,
  retrieved_at, language`. `retrieved_at` (UTC) in jeder Antwort.
- **Thematischer Filter `topic="education"`** — ausgewiesene Stichwort-Union
  (Freitext im Titel; Fedlex hat keine Sachgebiets-Taxonomie). Die Antwort nennt
  die tatsächlich gesuchten Begriffe (`message` + Markdown), damit klar ist,
  wonach *nicht* gesucht wurde. Sortierung nach kürzester Restfrist als Default.
- **Isoliertes `consultations`-Modul** — Vernehmlassungs-Logik (Uhr,
  Fristenberechnung, Modell, Query-Bausteine, Themenfilter) getrennt von der
  SR-/AS-/BBl-Schicht in `server.py`.
- **Neue Tests** (respx + injizierbare Uhr): korrektes `days_remaining`,
  Frist heute → `days_remaining == 0`, **Frist gestern → «Abgeschlossen», nicht
  in der Liste laufender Verfahren** (SPARQL-Frist-Grenze + Sprach-Dedupe im
  Query geprüft), Quelle «laufend» vs. Datum → Datum gewinnt, Themenfilter
  findet Bildungsvorlage inkl. ausgewiesener Strategie, Endpoint nicht
  erreichbar → erklärender Fehler statt leerem Resultat.

#### Known findings (live verifiziert 2026-07-20)
- **`jolux:Consultation` hat keine Sachgebiets-/Klassifikations-Taxonomie** —
  thematische Filterung ist ausschliesslich Freitext. Der Ankerbegriff
  «Volksschule» kommt in 0 Titeln vor (`bildung` 44, `topic="education"`-Union
  66; 42 aktuell offen).
- **SPARQL-Quirk:** `REGEX(LCASE(...), "a|b")` liefert auf dem Fedlex-Endpoint
  still **0** Treffer — Alternation daher über OR-verkettetes `CONTAINS`.
- **`eventEndDate` ist `xsd:date`** (reiner Kalendertag, keine Uhrzeit/TZ) →
  Vergleich gegen «heute in Europe/Zurich».
- Scope-Grenze dokumentiert: **nur Bund, keine kantonalen Vernehmlassungen**;
  kein Push-Mechanismus (MCP ist Pull-basiert).

#### Refactor
- **Geteilter SPARQL-/JSON-Client extrahiert** (`sparql_client.py`, vendored
  Portfolio-Baustein). Der bisherige `_execute_sparql`-Retry-Kern ist jetzt eine
  dünne Bindung an das wiederverwendbare Modul; `sparql_escape` / `val` daraus
  re-exportiert, `RETRYABLE_STATUS` entfernt. Verhalten unverändert
  (Retry/Backoff, Egress-Guard, `sparql_retry`-Log via Callback erhalten),
  öffentliche Namen stabil, 76 Tests grün. Die Datei ist **byte-identisch** zur
  Kopie in `swiss-environment-mcp` — bis ein installierbares `swiss-mcp-commons`
  (PyPI/OIDC) existiert, sind die Kopien synchron zu halten.

### Aus der nie ausgelieferten 1.1.0 (dokumentiert am 18.07.2026)

Erweitert den Server um zwei zusätzliche, ebenfalls SPARQL-basierte Datenquellen
— Vernehmlassungen (Fedlex) und die Terminologiedatenbank TERMDAT (via LINDAS).
Von 7 auf 12 Tools; 2 Resources unverändert. Vollständig rückwärtskompatibel:
die bestehenden `fedlex_*`-Tools und beide Resources bleiben unangetastet.

> Hinweis zur Version: Der zugrunde liegende Auftrag nannte `0.2.0`; da das Repo
> bereits auf `1.0.3` stand, wäre das ein Downgrade gewesen. Als
> semver-konformer Minor-Bump für eine rückwärtskompatible Funktionserweiterung
> ist es `1.1.0`.

#### Added
- **Vernehmlassungen (Fedlex, `jolux:Consultation`)** — drei neue Tools:
  - `fedlex_get_open_consultations` — Fristen-Monitoring; filtert **primär über
    `eventEndDate >= heute`**, nicht über den Status (die beiden Signale sind
    unabhängig). Sortiert nach Frist aufsteigend, optionaler `keyword`-Filter.
    Leeres Resultat liefert eine explizite Sachaussage inkl. Prüfzeitpunkt statt
    einer nackten leeren Liste.
  - `fedlex_search_consultations` — Volltextsuche über `eventTitle`/
    `eventDescription` mit Filtern für Status, Zeitraum (Frist) und
    federführendes Amt.
  - `fedlex_get_consultation` — Detail zu einer `eventId`: Fristen, Departement/
    Amt, Status, Vernehmlassungsunterlagen (`opinionHasDraftRelatedDocument`),
    betroffene Rechtsressource (`foreseenImpactToLegalResource`).
- **TERMDAT (LINDAS, schema.org)** — zwei neue Tools:
  - `termdat_lookup_term` — Begriff → Entsprechungen in de/fr/it/rm/en samt
    Definition.
  - `termdat_get_concept` — vollständiger Eintrag zu einer ID oder URI; akzeptiert
    ID, Konzept-URI und Term-URI mit Sprachsuffix und normalisiert intern.
- **Zweiter, isolierter SPARQL-Endpoint (LINDAS)** mit eigenem httpx-Client und
  eigenem Timeout (ARCH A / Isolationspflicht): Ein LINDAS-Ausfall lässt die
  `fedlex_*`-Tools unbeeinträchtigt und umgekehrt — getrennte Fehler-/Statusmeldung.
- **Retry-Logik** für transiente Fehler (HTTP 429/502/503/504, Timeout, Netzwerk)
  mit exponentiellem Backoff; deterministische Fehler (z.B. HTTP 400) werden
  nicht wiederholt.
- **TERMDAT-Attribution in jeder Response** (`source`-Feld + Markdown-Footer),
  inkl. des Teilbestand-Hinweises (77'692 von ~400'000 Einträgen).
- **Neue Tests** (respx-gemockt): Happy-Path je Tool, Retry bei 503, Timeout-/
  Netzwerk-Masking, Endpoint-Isolation, Status-Frist-Konflikt (Quirk 1),
  Consultation ohne `hasSubTask`, SPARQL-Escaping. Live-Tests gegen beide
  Endpoints unter `-m live` (aus CI ausgeschlossen).

#### Changed
- `fedlex://info`-Resource: Version, zweiter Endpoint, alle 12 Tools und die
  Isolationsnotiz ergänzt (Resource-URI unverändert).
- `handle_error` und der Response-Envelope tragen jetzt den betroffenen Dienst
  (`Fedlex` vs. `TERMDAT (LINDAS)`), damit ein isolierter LINDAS-Fehler nicht als
  Fedlex-Fehler gelesen wird.

#### Known findings
Live verifiziert am 18.07.2026:

**Vernehmlassungen (Fedlex)**
- Gesamtbestand `jolux:Consultation`: **2 553**.
- **48 von 2 553** Consultations haben keine `eventStartDate`/`eventEndDate`
  (kein `hasSubTask` mit Fristen) → `deadline: null`, kein Tool-Fehler.
- **Quirk 1:** Status «Laufend» (`consultation-status/2`) und eine Frist in der
  Zukunft sind **unabhängige Signale**. Es gibt «laufende» Einträge mit
  abgelaufener Frist. Die Tools filtern über die Frist und markieren
  Widersprüche mit `status_conflict: true` statt sie stillschweigend aufzulösen.
- `previousConsultationStatus` ist mit nur 234 Werten dünn besetzt und wird
  nicht als Filter verwendet.

**TERMDAT (LINDAS)**
- **Quirk 2 (Reality-Check):** Die Bundeskanzlei kommuniziert ~400 000 TERMDAT-
  Einträge; als Linked Data auf LINDAS liegen **77 692** (`schema.ld.admin.ch/Term`).
  Die Differenz ist nicht erklärt — vermutlich ist nur der validierte/freigegebene
  Teilbestand publiziert. Ein Negativtreffer bedeutet daher **nicht**, dass der
  Begriff in TERMDAT fehlt, sondern nur, dass er nicht im LINDAS-Teilbestand liegt.
  Dieser Hinweis steht in jeder TERMDAT-Response.
- **Quirk 3 (zwei URI-Ebenen):** Konzept-URIs (`…/termdat/40109`) tragen die
  bevorzugten Benennungen je Sprache, die Definition und via `schema:hasPart` die
  Synonym-/Varianten-Term-URIs mit Sprach- und Positionssuffix (`…/40109/3/de`).
  Beide Eingaben werden akzeptiert und intern auf die Konzept-ID normalisiert.
- **`rm` (Rätoromanisch)** ist im LINDAS-Teilbestand faktisch nicht besetzt
  (0 Namen) — als Zielsprache erlaubt, liefert aber in aller Regel keinen Treffer.

## [1.0.3] - 2026-06-07

### Fixed

- `mcp-name` im README deklariert, damit die MCP Registry die PyPI-Ownership
  auflösen kann. Der Marker muss in der Datei stehen, die `pyproject.toml` als
  `readme` deklariert — in `pyproject.toml` allein genügt er nicht.
  (`ce11fef`)

## [1.0.2] - 2026-06-07

### Added

- `mcp-name` in `pyproject.toml` für die Ownership-Prüfung der MCP Registry.
  (`d213966`)

### Changed

- Zweisprachige Dokumentation vereinheitlicht: Englisch als Hauptfassung,
  Deutsch verlinkt. (`49ff7f5`, PR #17)

## [1.0.0] - 2026-06-03

First production-ready release. Consolidates the `mcp-audit-skill` remediation
(Sprints 1–4); the post-remediation re-audit reports **production-ready**.

### Audit verification
- **Production-ready:** ✅ yes
- **Audit run-id:** `2026-06-03T100302-Z-fedlex-mcp`
- **Skill version:** `1.0.0` · **Catalog hash:** `091f446b2796…`
- **Check results:** 41 pass · 0 fail · 2 partial (non-blocking) · 1 n/a

### Added (Sprint 4 — infra & auth-posture remediation)
- **Hardened Kubernetes manifest** (`deploy/kubernetes.yaml`): non-root
  `securityContext`, read-only rootfs, dropped capabilities, seccomp
  RuntimeDefault (`SEC-007`); CPU/memory requests+limits (`SCALE-006`);
  `Mcp-Session-Id`-aware nginx Ingress routing + cookie affinity
  (`SCALE-002`/`SCALE-003`).
- **HAProxy edge config** (`deploy/haproxy.cfg`): `Mcp-Session-Id` stick-table
  (100k entries, 24h TTL, health-checked failover) for non-k8s multi-instance
  deployments (`SCALE-002`/`SCALE-003`).
- **Server-side tool allow-list** via `FEDLEX_ENABLED_TOOLS` (default-deny);
  complements an upstream gateway (`SEC-014`).
- **`docs/deployment.md`** (single-instance vs. horizontally-scaled guidance)
  and **ADR 0002** documenting auth/gateway posture: SEC-009 (N/A without auth,
  with re-audit trigger) and SEC-015 (gateway concern; SEC-022 as compensating
  control).

### Added (Sprint 3 audit remediation)
- **Structured response envelope** `FedlexResponse` for all 7 tools — `source`,
  `license`, `match_type`, `count`, `results[]` (each with `uri`/`url`
  provenance) plus a `markdown` field that preserves the human-readable
  rendering (`SDK-002`, `CH-004`).
- **Tool-definition hash pinning** — `tool-definitions.lock.json` +
  `scripts/snapshot_tools.py` + a test that fails on silent tool drift
  (`SEC-022`).
- **Optional OpenTelemetry tracing** (`pip install 'fedlex-mcp[otel]'`):
  per-tool spans and httpx auto-instrumentation, activated only when
  `OTEL_EXPORTER_OTLP_ENDPOINT` is set — otherwise a no-op (`OBS-006`).
- **Egress host assertion** `assert_host_allowed()` before every request, and
  ADR `docs/adr/0001-egress-trifecta-and-dns.md` documenting the egress
  allow-list, lethal-trifecta posture and the accepted DNS-rebinding risk
  (`SEC-021`, `SEC-019`, `SEC-005`).

### Note
Tools now return JSON (structured content) in addition to Markdown; clients
that previously rendered the Markdown string will see the structured envelope.

### Added (Sprint 2 audit remediation)
- **Structured logging** with `structlog` — JSON to stderr, per-call bound
  context (`OBS-003`, keeps stdout clean for stdio per `OBS-004`).
- **MCP `Context` injection** in all tools (`ctx.info`/`ctx.error`) for
  client-visible progress and error reporting (`SDK-003`).
- **Use-case tags** (`<use_case>`/`<important_notes>`/`<example>`) in every tool
  description to improve LLM tool selection (`ARCH-002`).
- Empty results now carry a `match_type: none` marker (`ARCH-003`).
- `.gitignore` and a gitleaks secret-scan CI workflow (`ARCH-005`).
- `.github/dependabot.yml` (monthly pip + actions updates) and a README
  "MCP Protocol Version" section (`ARCH-012`).
- README "Project Phase" section declaring Phase 1 / read-only (`OPS-003`).
- Multi-stage, non-root `Dockerfile` + `.dockerignore` (`SCALE-004`).

### Changed
- **Shared HTTP client via FastMCP lifespan** — a single `httpx.AsyncClient` is now
  created once per server lifecycle instead of per tool call (audit `SDK-001`).
- **Settings/env-driven transport** — transport, host, port and CORS origins are
  configured via `Settings` / `FEDLEX_*` env vars instead of an `argv` flag
  (`ARCH-004`, `SCALE-001`). The `--http` flag still works for backward compatibility.

### Added
- **CORS for Streamable HTTP** exposing the `Mcp-Session-Id` header, required for
  browser-based MCP clients (`SDK-004`).
- **Input hardening** — `keywords`/`sr_number` now carry whitelist patterns and all
  user input is escaped before SPARQL interpolation, closing a query-injection
  vector (`SEC-004`, `SEC-018`).
- **Code-layer egress allow-list** (`ALLOWED_EGRESS_HOSTS`) and stderr logging
  (`SEC-021`, `OBS-004`).
- **Real test suite** — 40 offline `respx`-mocked unit tests (tools, validation,
  error masking) plus a `live` smoke test (`OPS-001`).

### Fixed
- Error handler no longer echoes raw exception detail to the LLM; internals are
  logged server-side only (`OBS-001`, `OBS-002`).

## [0.1.0] - 2026-03-31

### Added
- Initial release
- **7 tools**: `fedlex_search_laws`, `fedlex_get_law_by_sr`, `fedlex_get_recent_publications`, `fedlex_get_upcoming_changes`, `fedlex_search_gazette`, `fedlex_get_law_history`, `fedlex_search_treaties`
- **2 resources**: `fedlex://sr/{sr_number}`, `fedlex://info`
- SPARQL-powered access to Fedlex linked data endpoint
- 4 language support (de, fr, it, rm)
- Dual transport: stdio (Claude Desktop) + Streamable HTTP (cloud/Render.com)
- GitHub Actions CI (Python 3.11, 3.12, 3.13)
- Bilingual documentation (EN/DE)
