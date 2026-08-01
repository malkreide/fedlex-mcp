# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

> **Einordnung korrigiert am 01.08.2026.** Die beiden Blöcke unten standen hier
> als `[1.1.0]` und `[1.2.0]`, obwohl keine der beiden Versionen je ausgeliefert
> wurde: kein Tag, kein PyPI-Upload, kein GitHub-Release. Zuletzt veröffentlicht
> ist **1.0.3** (PyPI, Tag `v1.0.3`). Der Inhalt ist unverändert übernommen — nur
> die Einordnung war falsch. `pyproject.toml` und `server.json` stehen weiterhin
> auf 1.2.0; das ist der vorbereitete Bump für den nächsten Release.

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


### Behoben

- **`mcp` auf `<2` begrenzt.** `mcp` 2.0.0, veröffentlicht am 28.07.2026, hat
  `mcp.server.fastmcp` entfernt — genau das Modul, das dieser Server importiert.
  Mit dem bisherigen offenen `>=1.28.1` wählte jede frische Auflösung 2.0.0 und
  scheiterte beim Import mit `ModuleNotFoundError`, in der CI ebenso wie bei
  jedem `pip install`. In beide Richtungen verifiziert: 2.0.0 scheitert, `<2`
  löst auf 1.29.0 auf und importiert sauber. Die Migration auf die 2.x-API
  (`mcp.server.mcpserver`) bleibt eine eigene, bewusste Aufgabe.

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
