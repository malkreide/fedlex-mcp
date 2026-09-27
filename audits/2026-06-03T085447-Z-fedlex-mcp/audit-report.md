# MCP-Server Audit-Report — `fedlex-mcp`

**Audit-Datum:** 2026-06-03
**Skill-Version:** 1.0.0
**Catalog-Version:** 68 checks / hash 091f446b

> **Nachträge.** Dieser Report ist der Stand vom 2026-06-03 und bleibt unverändert.
> Spätere Statusänderungen stehen als datierter Nachtrag in der jeweiligen Datei
> unter `findings/`:
>
> | Finding | Stand | Datum | Nachweis |
> |---|---|---|---|
> | OBS-001 | Resolved | 2026-09-27 | malkreide/fedlex-mcp#86 |
> | SDK-003 | Logging-Teil gegenstandslos (SEP-2577), Progress offen | 2026-09-27 | malkreide/fedlex-mcp#85 |

---

## 1. Executive Summary

Server `fedlex-mcp` wurde gegen 44 anwendbare Best-Practice-Checks geprüft. 15 bestanden, 22 Findings dokumentiert (2 critical, 12 high, 8 medium, 0 low). Production-Readiness: NICHT erreicht — blockierend: OPS-001, SDK-001, SDK-004.

**Production-Readiness:** NO

---

## 2. Profil-Snapshot

| Feld | Wert |
|---|---|
| Server-Name | `fedlex-mcp` |
| Audit-Datum | 2026-06-03 |
| Skill-Version | 1.0.0 |
| Catalog-Version | 68 checks / hash 091f446b |
| transport | `dual` |
| auth_model | `none` |
| data_class | `Public Open Data` |
| write_capable | `False` |
| deployment | `['local-stdio', 'Render']` |
| uses_sampling | `False` |
| tools_make_external_requests | `True` |
| stadt_zuerich_context | `False` |
| schulamt_context | `False` |
| data_source.is_swiss_open_data | `True` |

---

## 3. Applicability

### Status pro Kategorie

| Kategorie | Pass | Fail | Partial | Todo | N/A |
|---|---|---|---|---|---|
| ARCH | 6 | 0 | 5 | 0 | 0 |
| CH | 1 | 0 | 0 | 0 | 0 |
| OBS | 1 | 2 | 2 | 0 | 0 |
| OPS | 1 | 1 | 1 | 0 | 0 |
| SCALE | 0 | 1 | 1 | 3 | 0 |
| SDK | 0 | 2 | 2 | 0 | 0 |
| SEC | 6 | 0 | 5 | 4 | 0 |
| **Total** | **15** | **6** | **16** | **7** | **0** |

---

## 4. Findings-Übersicht

_Policy: `fail-or-partial`_

| ID | Category | Severity | Status |
|---|---|---|---|
| ARCH-005 | ARCH | critical | partial |
| SEC-004 | SEC | critical | partial |
| ARCH-004 | ARCH | high | partial |
| OBS-001 | OBS | high | partial |
| OBS-002 | OBS | high | partial |
| OPS-001 | OPS | high | fail |
| OPS-003 | OPS | high | partial |
| SCALE-001 | SCALE | high | partial |
| SDK-001 | SDK | high | fail |
| SDK-004 | SDK | high | fail |
| SEC-005 | SEC | high | partial |
| SEC-018 | SEC | high | partial |
| SEC-021 | SEC | high | partial |
| SEC-022 | SEC | high | partial |
| ARCH-002 | ARCH | medium | partial |
| ARCH-003 | ARCH | medium | partial |
| ARCH-012 | ARCH | medium | partial |
| OBS-003 | OBS | medium | fail |
| OBS-006 | OBS | medium | fail |
| SCALE-004 | SCALE | medium | fail |
| SDK-002 | SDK | medium | partial |
| SDK-003 | SDK | medium | partial |

**Gesamt:** 22 Findings

---

## 5. Detail-Findings

### ARCH-002

## Finding: ARCH-002 — Tool-Beschreibung mit Use-Case-Tags

**Severity:** medium
**Status:** Open
**Server:** fedlex-mcp
**Check-Reference:** ARCH-002
**PDF-Reference:** Sec 2.2
**Verifikations-Status:** partial

### Observed Behavior

- Tool-Docstrings > 100 Zeichen, mit Args/Returns/Use-Case-Prosa

### Gaps / Abweichung vom Standard

- Keine strukturierten <use_case>/<important_notes>/<example>-Tags (0 Treffer)
- Beschreibungskontext steckt nur im Python-Docstring, nicht in description=

### Risk Description

LLMs wählen Tools nicht über exakte Namens-Treffer, sondern über semantische Embeddings der Tool-Beschreibung. Eine Beschreibung wie `"Searches database"` lässt das Modell zwischen drei `getX`-Tools rätseln. Eine Beschreibung mit explizitem Use-Case-Tag, Trigger-Phrasen und Negativ-Hinweisen («NICHT verwenden für…») reduziert Halluzinationen drastisch. Die Best-Practice-Konvention im PDF nutzt XML-artige Tags innerhalb der Description: - `<use_case>` — Wann soll das Tool verwendet werden? - `<important_notes>` — Caveats, Side-Effects, Limitierungen - `<example>` — Konkrete Beispiel-Inputs Das …

### Remediation

```diff
  @mcp.tool(
      name="searchEducationStats",
-     description="Search education statistics."
+     description=(
+         "Sucht in den städtischen Bildungsstatistiken nach Kennzahlen "
+         "(Klassengrösse, Lehrer-Schüler-Verhältnis, Anteil DaZ, etc.).\n\n"
+         "<use_case>Politische / journalistische Recherche, "
+         "Schulamts-interne Reportings, Pädagogik-Analysen.</use_case>\n\n"
+         "<important_notes>Daten werden quartalsweise aktualisiert. "
+         "Personendaten sind nicht abrufbar — nur aggregierte "
+         "Kennzahlen.</important_notes>"
+     ),
  )
```

### Effort Estimate

S — Pro Tool 5–10 Minuten. Bei 10 Tools: ~1 Tag.


### ARCH-003

## Finding: ARCH-003 — «Not Found» Anti-Pattern: Heuristiken statt leerer Antworten

**Severity:** medium
**Status:** Open
**Server:** fedlex-mcp
**Check-Reference:** ARCH-003
**PDF-Reference:** Sec 2.2
**Verifikations-Status:** partial

### Observed Behavior

- Leere Ergebnisse liefern handlungsweisende Tipps statt nur [] (z.B. server.py:281-288)

### Gaps / Abweichung vom Standard

- Kein match_type-Feld (exact/fuzzy/none)
- Kein Fuzzy-/Suggestion-Mechanismus bei 0 Treffern

### Risk Description

LLMs reagieren empirisch nachweisbar empfindlich auf negativ-framing in Tool-Responses. Eine Antwort wie `"No results found"` oder `[]` ohne Kontext führt häufig zu einer von zwei Failure-Modes: 1. **Halluzination:** Das Modell konstruiert eine Antwort aus Trainingsdaten, statt zuzugeben, dass es keine Information hat. 2. **Sackgasse:** Das Modell bricht die Aufgabe ab, statt mit alternativen Strategien (verwandte Begriffe, andere Tools) weiterzumachen. Der Best-Practice-Standard fordert: Wenn ein Tool keine exakten Treffer findet, soll es **partielle / heuristische / verwandte Ergebnisse** …

### Remediation

```diff
  @mcp.tool()
  async def find_school(name: str) -> list:
      results = await db.find(name)
-     if not results:
-         return []
+     if not results:
+         fuzzy = await db.find_fuzzy(name, threshold=0.7)
+         suggestions = await db.popular_school_names_starting_with(name[:3])
+         return {
+             "results": fuzzy[:5],
+             "match_type": "fuzzy" if fuzzy else "none",
+             "note": (
+                 f"Keine exakten Treffer für '{name}'. "
+                 f"{'Ähnliche Schulen aufgeführt.' if fuzzy else ''} "
+                 f"Häufige Schulnamen: {', '.join(suggestions[:5])}"
+             ),
+         }
      return {"results": results, "match_type": "exact"}
```

### Effort Estimate

S — Pro Tool ~30 Minuten. Bei 10 Such-Tools: 1 Tag.


### ARCH-004

## Finding: ARCH-004 — Inversion of Control: Transport-agnostische Server-Logik

**Severity:** high
**Status:** Open
**Server:** fedlex-mcp
**Check-Reference:** ARCH-004
**PDF-Reference:** Sec 2.1
**Verifikations-Status:** partial

### Observed Behavior

- Dual-Transport stdio + streamable-http vorhanden (server.py:876-884)
- Tool-Handler sind transport-agnostisch: kein request./stdin-Zugriff, nur Pydantic-Params

### Gaps / Abweichung vom Standard

- Transport-Wahl via sys.argv-Flag statt ENV-Var/Pydantic-Settings
- Kein Settings-Objekt, keine lifespan-Funktion

### Risk Description

Die MCP-Spezifikation trennt strikt zwischen Data Layer (JSON-RPC 2.0, Tools/Resources/Prompts) und Transport Layer (stdio / Streamable HTTP / SSE). Der Best-Practice-Standard verlangt, dass die Geschäftslogik des Servers diese Trennung respektiert: Tool-Handler müssen **transport-agnostisch** sein. Derselbe `searchData()`-Tool-Handler muss identisch funktionieren, egal ob er via stdio (Claude Desktop) oder SSE (Cloud-Deployment) aufgerufen wird. **Warum:** 1. **Dual-Transport-Support:** Portfolio-Server müssen sowohl lokal (stdio) als auch in der Cloud (SSE) laufen. Ohne IoC braucht man zwei …

### Remediation

Migrationsweg von monolithischem Setup zu IoC:

```diff
+ from pydantic_settings import BaseSettings
+ from contextlib import asynccontextmanager
+
+ class Settings(BaseSettings):
+     transport: str = "stdio"
+     host: str = "127.0.0.1"
+     port: int = 8000
+
+ @asynccontextmanager
+ async def lifespan(server):
+     # Shared setup für alle Transports
+     server.state.http_client = httpx.AsyncClient(timeout=30)
+     try:
+         yield
+     finally:
+         await server.state.http_client.aclose()
+
- mcp = FastMCP("server")
+ settings = Settings()
+ mcp = FastMCP("server", lifespan=lifespan)

  @mcp.tool()
- async def search(query: str, request: Request):
-     ua = request.headers["User-Agent"]
-     ...
+ async def search(query: str, ctx: Context):
+     client_name = ctx.client_info.name
+     ...

  if __name__ == "__main__":
-     mcp.run(transport="stdio")
+     if settings.transport == "sse":
+         mcp.settings.host = settings.host
+         mcp.settings.port = settings.port
+     mcp.run(transport=settings.transport)
```

### Effort Estimate

M — 1–3 Tage. Refactoring der Transport-Auswahl, Migration aller `request`-Zugriffe auf `ctx`, Testing in beiden Modi.


### ARCH-005

## Finding: ARCH-005 — Keine Hardcoded Secrets: Env-Vars / Secret Manager only

**Severity:** critical
**Status:** Open
**Server:** fedlex-mcp
**Check-Reference:** ARCH-005
**PDF-Reference:** Sec 2.1
**Verifikations-Status:** partial

### Observed Behavior

- Keine hardcoded Secrets im Code (Server benoetigt keinerlei Credentials)
- Kein os.environ-Secret-Loading noetig (No-Auth-Server)

### Gaps / Abweichung vom Standard

- Kein .gitignore im Repo vorhanden (.env waere nicht ignoriert)
- Kein CI-Secret-Scan (gitleaks/trufflehog)
- Reales Leak-Risiko jedoch gering, da keine Secrets existieren

### Risk Description

Hardcoded Secrets (API-Keys, Passwörter, Tokens, Connection-Strings, Encryption-Keys) im Source-Code sind die häufigste vermeidbare Sicherheitsschwäche in MCP-Server-Repositories. Sobald das Repo öffentlich ist (oder versehentlich öffentlich wird), oder ein Mitarbeiter aus dem Team ausscheidet, sind alle Secrets kompromittiert. GitHub's Secret-Scanning fängt einen Teil davon ab — aber: (1) nicht alle Pattern werden erkannt, (2) Custom-API-Keys (z.B. interne Schulamt-APIs) sind unbekannt, (3) selbst nach Erkennung ist der Schlüssel bereits im Git-Verlauf und muss neu ausgestellt werden. …

### Remediation

### Schritt 1: Bestehende Secrets identifizieren und ersetzen

```bash
# Lokale Suche (vor jeglichem Push)
gitleaks detect --source . --verbose

# Falls schon committed: History-Rewrite ZUSÄTZLICH zur Schlüssel-Rotation
# Wichtig: rotation FIRST, history-rewrite zweitrangig
```

### Schritt 2: Migration zu Pydantic-Settings

```python
# Vorher
API_KEY = "sk-1234..."

# Nachher
from pydantic import SecretStr
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    api_key: SecretStr
    model_config = {"env_file": ".env", "extra": "forbid"}

settings = Settings()
# Im Code: settings.api_key.get_secret_value()
```

### Schritt 3: `.env.example` mit Platzhaltern

```bash
# .env.example (committet)
API_KEY=replace-with-real-key
DATABASE_URL=postgresql://user:pass@localhost/dbname
OAUTH_CLIENT_SECRET=at-least-32-characters-long-secret

# .env (NICHT committet, in .gitignore)
API_KEY=sk-actual-real-key
...
```

### Schritt 4: Production-Secret-Manager (höhere Reife)

| Plattform | Mechanismus |
|---|---|
| Railway | Project-Variables (verschlüsselt at-rest) |
| Render | Environment-Groups |
| Kubernetes | `Secret`-Objects + `secretKeyRef` in Pod-Spec |
| Self-Hosted | HashiCorp Vault, AWS Secrets Manager (EU-Region!), GCP Secret Manager |

```python
# AWS Secrets Manager (EU-Region für DSG, siehe CH-001)
import boto3
import json

def load_secret(name: str) -> dict:
    client = boto3.client("secretsmanager", region_name="eu-central-1")
    response = client.get_secret_value(SecretId=name)
    return json.loads(response["SecretString"])

secrets = load_secret("schulamt-mcp/production")
api_key = secrets["api_key"]
```

### Schritt 5: CI-Scan einrichten

Siehe Modus 5 oben.

### Schritt 6: Pre-Commit-Hook lokal

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.0
    hooks:
      - id: gitleaks
```

```bash
pre-commit install
# Verhindert Commits mit erkannten Secrets lokal
```

### Effort Estimate

S–M — Bei sauberem Repo: < 1 Tag (Settings-Migration + CI-Setup). Bei Repo mit Secret-Leak in History: 2–3 Tage (Rotation aller Schlüssel, History-Rewrite, Audit aller Forks/Clones).


### ARCH-012

## Finding: ARCH-012 — protocolVersion-Pinning + CHANGELOG + SDK-Update-Disziplin

**Severity:** medium
**Status:** Open
**Server:** fedlex-mcp
**Check-Reference:** ARCH-012
**PDF-Reference:** Anhang A9
**Verifikations-Status:** partial

### Observed Behavior

- CHANGELOG.md vorhanden

### Gaps / Abweichung vom Standard

- protocolVersion nicht explizit gepinnt
- Keine README-Sektion MCP Protocol Version
- Kein Dependabot/Renovate fuer SDK-Updates

### Risk Description

Die MCP-Spec hat in 13 Monaten vier Major-Updates erlebt (2024-11, 2025-03, 2025-06, 2025-11). Das ist eine ungewöhnlich hohe Velocity für einen Industriestandard. Konkrete Folgen für Server-Maintainer: 1. **Tool Annotations** kamen erst 2025-03-26 2. **OAuth Resource Server** mit RFC 8707 wurde erst 2025-06-18 verpflichtend 3. **WebSocket-Transport** wurde 2025-03 abgeschafft, durch Streamable HTTP ersetzt Wer die `protocolVersion` als «latest» (oder gar nicht) pinnt, riskiert dass: - Ein SDK-Update auf einer neuen Spec-Version den Server bricht (Client erwartet altes Protokoll) - …

### Remediation

### Schritt 1: protocolVersion pinnen

```diff
+ from importlib.metadata import version

  mcp = FastMCP(
      name="zh-education-mcp",
+     protocol_version="2025-06-18",
  )
```

### Schritt 2: CHANGELOG initialisieren

Wenn nicht vorhanden, mit Template starten und retroaktiv Major-Versionen dokumentieren (mindestens letzte 3).

### Schritt 3: Dependabot konfigurieren

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "monthly"
    open-pull-requests-limit: 5
```

### Schritt 4: Quartalsweise Spec-Review

Im Audit-Tracker (Notion) oder GitHub Issues ein recurring Reminder für quartalsweise Spec-Velocity-Review:

- Was hat sich an der MCP-Spec geändert seit letztem Release?
- Welche Server müssen ihre `protocolVersion` aktualisieren?
- Gibt es Compliance-relevante Spec-Änderungen?

### Effort Estimate

S — < 1 Tag pro Server. Pinning + CHANGELOG-Template + Dependabot-Setup.


### OBS-001

## Finding: OBS-001 — Protocol vs. Execution Errors: korrekte Trennung

**Severity:** high
**Status:** Open
**Server:** fedlex-mcp
**Check-Reference:** OBS-001
**PDF-Reference:** Sec 6.1
**Verifikations-Status:** partial

### Observed Behavior

- handle_error faengt httpx-Fehler ab und liefert handlungsweisende Meldungen (server.py:118-136)

### Gaps / Abweichung vom Standard

- Execution-Errors werden als Plain-String zurueckgegeben, nicht als isError:true Tool-Result
- Keine Tests fuer Execution- bzw. Protocol-Error-Pfade

### Risk Description

Die MCP-Spezifikation fordert eine strikte Trennung zwischen zwei Fehler-Typen. Werden sie verwechselt, kann das LLM den Fehler nicht korrekt interpretieren und bricht in eine Halluzinations- oder Sackgassen-Schleife. | Fehler-Typ | Beispiele | Format | |---|---|---| | **Protocol Error** | Tool existiert nicht, Schema-Mismatch, JSON-Parsing-Fehler, interner Server-Crash beim Routing | Standard JSON-RPC Error Response (`{"jsonrpc": "2.0", "error": {...}}`) | | **Execution Error** | API-Ratenlimit, Datei nicht gefunden, ungültige Geschäfts-Parameter, Drittanbieter-API down | Tool-Result mit …

### Remediation

```diff
+ from mcp.types import TextContent
+
  @mcp.tool()
  async def query_database(query: str) -> dict:
-     # FAIL: alle Exceptions werden zu JSON-RPC-Errors
-     conn = await asyncpg.connect(DATABASE_URL)
-     return {"rows": await conn.fetch(query)}
+     try:
+         conn = await asyncpg.connect(DATABASE_URL)
+         try:
+             rows = await conn.fetch(query)
+             return {"rows": [dict(r) for r in rows]}
+         finally:
+             await conn.close()
+     except asyncpg.PostgresSyntaxError as e:
+         # Execution Error: Query-Problem ist Aufgabe des LLMs zu lösen
+         return {
+             "isError": True,
+             "content": [TextContent(
+                 type="text",
+                 text=f"SQL syntax error: {str(e)}. Try simplifying the query."
+             )],
+         }
+     except asyncpg.PostgresConnectionError:
+         # Protocol-nahe: Server ist degraded
+         raise McpError(code=-32603, message="Database temporarily unavailable")
```

### Effort Estimate

M — 1–3 Tage. Pro Tool muss der Error-Pfad reviewed werden. Bei vielen Tools (>10) entsprechend aufwändiger.


### OBS-002

## Finding: OBS-002 — Mask Error Details: keine Stacktraces / SQL ans LLM

**Severity:** high
**Status:** Open
**Server:** fedlex-mcp
**Check-Reference:** OBS-002
**PDF-Reference:** Sec 6.2
**Verifikations-Status:** partial

### Observed Behavior

- handle_error gibt generische, gemappte Meldungen (kein Stacktrace)

### Gaps / Abweichung vom Standard

- FastMCP ohne mask_error_details=True initialisiert
- Fallback-Zweig f"Fehler: {type(e).__name__}: {e}" (server.py:136) kann interne Exception-Details ans LLM leaken

### Risk Description

Wenn Tool-Errors Stacktraces, SQL-Syntax, Datei-Pfade oder gar Credentials enthalten, fliesst dieser Inhalt in den LLM-Kontext und damit potentiell ins User-Sichtbare zurück. Das ist Information Disclosure: Angreifer mit User-Zugriff erfahren über provozierte Errors die Server-Architektur, DB-Schema, gemountete Pfade, sogar geleakte Tokens (z.B. in `Authorization`-Headern, die im Stacktrace landen). FastMCP bietet `mask_error_details=True`: Server-Errors werden auf eine generische Message reduziert (`"An error occurred"`), Original-Details landen nur im Server-Log. Trade-off: LLM kann nicht …

### Remediation

```diff
  mcp = FastMCP(
      "server",
+     mask_error_details=True,
  )

  @mcp.tool()
  async def search(query: str):
      try:
          return await db.search(query)
-     except Exception as e:
-         return {"error": str(e), "traceback": traceback.format_exc()}
+     except UserInputError as e:
+         return {"isError": True, "content": [
+             TextContent(type="text", text=f"Invalid input: {e.user_message}")
+         ]}
+     except Exception:
+         logger.exception("Unhandled error in search tool")
+         raise  # mask_error_details greift, generische Message ans LLM
```

### Effort Estimate

S — < 1 Tag pro Server.


### OBS-003

## Finding: OBS-003 — Structured Logging mit RFC 5424 Severity-Stufen

**Severity:** medium
**Status:** Open
**Server:** fedlex-mcp
**Check-Reference:** OBS-003
**PDF-Reference:** Sec 6.3
**Verifikations-Status:** fail

### Observed Behavior

- Keinerlei Logging im Code (kein logger/structlog/loguru), nicht in dependencies

### Gaps / Abweichung vom Standard

- Kein Structured Logger
- Keine RFC-5424-Severity-Stufen
- Kein bound context pro Tool-Call

### Risk Description

MCP-Server-Logs müssen strukturiert sein (JSON oder logfmt), nicht plaintext. Das ermöglicht Aggregation in Datadog/Splunk/Loki ohne Regex-Parsing, korrelierte Suche über Correlation-IDs, und konsistente Severity-Filterung. Der MCP-Standard nutzt RFC 5424's 8 Severity-Stufen: `debug`, `info`, `notice`, `warning`, `error`, `critical`, `alert`, `emergency`. Über das `notifications/message`-Event können Logs auch an den Client weitergereicht werden — der Client kann via `logging/setLevel` dynamisch filtern. Für Python ist `structlog` der Standard, für TypeScript `pino`.

### Remediation

```diff
- import logging
- logger = logging.getLogger(__name__)
+ import structlog
+ logger = structlog.get_logger("mcp.server")

  @mcp.tool()
  async def search(query: str, ctx):
-     logger.info(f"Searching for {query}")
-     result = await api.search(query)
-     logger.info(f"Got {len(result)} results")
+     log = logger.bind(tool="search", query=query, session=ctx.session_id)
+     log.info("tool_invoked")
+     result = await api.search(query)
+     log.info("tool_succeeded", count=len(result))
      return result
```

### Effort Estimate

S — < 1 Tag pro Server.


### OBS-006

## Finding: OBS-006 — OpenTelemetry Distributed Tracing pro Tool-Call

**Severity:** medium
**Status:** Open
**Server:** fedlex-mcp
**Check-Reference:** OBS-006
**PDF-Reference:** Anhang B10
**Verifikations-Status:** fail

### Observed Behavior

- Kein OpenTelemetry SDK, kein Tracing

### Gaps / Abweichung vom Standard

- Kein TracerProvider/OTLP-Exporter
- Keine Span-Instrumentierung pro Tool-Call

### Risk Description

OBS-005 deckt Audit-Logs für SIEM-Integration ab — Security-fokussiert. OBS-006 ergänzt das auf der **Performance- und Behavior-Seite**: jeder Tool-Call wird als OpenTelemetry-Span erfasst, mit: - **Trace-ID** über die ganze LLM-Host → Gateway → Server → Backend-Kette - **Tool-Name** als Span-Name - **User-Identity** als Span-Attribut (aus `ctx.user_claims`) - **Latenz** der einzelnen Hop-Schritte - **Token-Count** falls Sampling involviert - **Backend-API-Latenzen** als Child-Spans Dieser Check ist `medium`, weil ohne Tracing zwar der Server funktioniert, aber drei wichtige Forensik- und …

### Remediation

### Schritt 1: SDK-Installation

```toml
# pyproject.toml
[project.dependencies]
"opentelemetry-api" = "^1.21"
"opentelemetry-sdk" = "^1.21"
"opentelemetry-exporter-otlp" = "^1.21"
"opentelemetry-instrumentation-httpx" = "^0.42b0"
```

### Schritt 2: Setup-Modul

```python
# src/server_name/observability.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource
# ...

def setup_tracing():
    resource = Resource.create({
        "service.name": os.environ.get("OTEL_SERVICE_NAME", "schulamt-mcp"),
        "deployment.environment": os.environ.get("ENVIRONMENT", "development"),
    })
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    HTTPXClientInstrumentor().instrument()
```

### Schritt 3: Decorator anwenden

`@traced_tool` als Standard auf alle Tool-Decorators stacken.

### Schritt 4: OTLP-Backend wählen

Für Schulamt-Kontext: Datadog (DSG-konform mit `DD_SITE=datadoghq.eu`), Grafana Tempo (selbst-gehostet, OpenBao-Compatible), oder Honeycomb (EU-Region).

### Effort Estimate

M — 1–3 Tage. SDK-Setup + Decorator + Backend-Konfiguration + Tests.


### OPS-001

## Finding: OPS-001 — Test-Strategie: Unit-Tests mocked + Live-Tests gemarkert

**Severity:** high
**Status:** Open
**Server:** fedlex-mcp
**Check-Reference:** OPS-001
**PDF-Reference:** Anhang C1
**Verifikations-Status:** fail

### Observed Behavior

- respx in dev-deps, live-Marker registriert (pyproject), CI laeuft pytest -m 'not live'

### Gaps / Abweichung vom Standard

- tests/test_server.py enthaelt nur 2 triviale Unit-Tests (Regex + Import) + 1 leeren Live-Placeholder
- Weit unter '5 Unit-Tests pro Tool / 1 Live-Test pro Tool'
- Keine HTTP-Mock-Tests trotz respx-Abhaengigkeit

### Risk Description

Aus dem Sormena-Pattern bewährt: zwei Test-Kategorien mit klarer Trennung. | Kategorie | Zweck | Wann ausgeführt | Mock | Speed | |---|---|---|---|---| | **Unit-Tests** | Server-Logik isoliert prüfen | CI bei jedem PR | respx-mocked HTTP | ~1s pro Test | | **Live-Tests** | Echte API-Antworten gegen aktuelle Schnittstellen prüfen | Manuell, nightly, vor Release | keiner | 5-30s pro Test | Die Trennung ist nicht akademisch — sie löst drei reale Probleme: 1. **CI-Stabilität:** Live-Tests scheitern bei API-Outages der Datenquelle (z.B. opendata.swiss-Wartung). Wenn alle Tests in CI laufen, wird …

### Remediation

### Schritt 1: pyproject.toml-Marker registrieren

```toml
[tool.pytest.ini_options]
markers = [
    "live: tests against real APIs (manual, nightly only)",
]
```

### Schritt 2: respx als Dev-Dependency

```toml
[project.optional-dependencies]
dev = [
    "pytest >= 7.4",
    "pytest-asyncio >= 0.21",
    "pytest-cov >= 4.1",
    "respx >= 0.20",
]
```

### Schritt 3: Unit-Test-Suite aufbauen

Pro Tool mindestens drei Tests:
- Happy-Path (200, expected schema)
- Error-Path (4xx/5xx)
- Edge-Case (leere Antwort, malformed input)

### Schritt 4: CI-Workflow updaten

`.github/workflows/test.yml`:

```yaml
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-python@v6
        with:
          python-version: "3.11"
      - run: pip install -e ".[dev]"
      - run: pytest -m "not live" --cov=src
```

### Schritt 5: Nightly-Live-Workflow

Wie im Pass-Pattern Modus 4.

### Effort Estimate

M — 1–3 Tage Initial-Setup. Tests-Schreiben skaliert mit Tool-Anzahl.


### OPS-003

## Finding: OPS-003 — Phasenarchitektur: Read-only First, dann Write, dann Multi-Agent

**Severity:** high
**Status:** Open
**Server:** fedlex-mcp
**Check-Reference:** OPS-003
**PDF-Reference:** Anhang C4
**Verifikations-Status:** partial

### Observed Behavior

- Tools sind durchgaengig read-only (entspricht implizit Phase 1)

### Gaps / Abweichung vom Standard

- Keine explizite Phasen-Deklaration im README
- Kein Roadmap-File

### Risk Description

Der Anhang sagt klar: «Die häufigste Ursache von MCP-Sicherheitsvorfällen 2025/26 war: ‹Wir haben gleich Schreibzugriffe gebaut, weil es ging.›» Disziplin: jeder Server durchläuft drei Phasen. Übersprungene Phasen produzieren Sicherheits- und Compliance-Vorfälle. | Phase | Dauer | Zustand | Was wird gebaut | Was darf NICHT | |---|---|---|---|---| | **Phase 1** | Wochen | Read-only-Wrapper | Tools mit `readOnlyHint: true`, OAuth, Gateway davor, Doku, Tests | Kein Write, keine Compensating Actions, kein Multi-Agent | | **Phase 2** | Monate | Anreicherung | Semantic Layer, Identity Resolution, …

### Remediation

### Schritt 1: Phase-Audit pro Server

Pro Server im Portfolio:

| Frage | Antwort |
|---|---|
| Hat der Server destruktive Tools? | ja → mindestens Phase 3 |
| Hat der Server Semantic Layer / Federation? | ja → mindestens Phase 2 |
| Sonst | Phase 1 |

### Schritt 2: Phase-Sektion ins README

Mit Status-Tabelle wie im Pass-Pattern Modus 1.

### Schritt 3: Roadmap erstellen

Mit Phase-Voraussetzungen als Tasks. Falls aktueller Server in Phase 2 oder 3 ist und Phase-1-Voraussetzungen fehlen: Findings im Audit-Tracker dokumentieren, retroaktiv schliessen.

### Schritt 4: Phase-Gate als Notion-Workflow

In Notion-Audit-Tracker-Schema (`a2736a65-...`) ein Feld «Phase» (Single-Select: 1, 2, 3) mit klaren Übergangs-Anforderungen.

### Effort Estimate

S — < 1 Tag pro Server für Initial-Phase-Deklaration. M — Wochen für Phase-Übergänge mit allen Compensating-Action-Anforderungen.


### SCALE-001

## Finding: SCALE-001 — Streamable HTTP statt stdio für Cloud-Deployments

**Severity:** high
**Status:** Open
**Server:** fedlex-mcp
**Check-Reference:** SCALE-001
**PDF-Reference:** Sec 5.1
**Verifikations-Status:** partial

### Observed Behavior

- Cloud nutzt streamable-http (server.py:882), keine WebSocket-Implementierung

### Gaps / Abweichung vom Standard

- Transport-Selektion via CLI-Flag --http statt ENV-Var

### Risk Description

stdio-Transport ist für lokale Single-User-Sessions konzipiert: ein Subprozess, eine Stdin/Stdout-Pipe, ein Client. Cloud-Deployments mit Multi-User-Zugriff können stdio nicht sinnvoll bedienen — der TCP-Bruch killt die Pipe, kein Failover möglich. Streamable HTTP / SSE sind die Cloud-Standards 2026; sie unterstützen Reconnect via Event-IDs, Multi-User, Standard-HTTP-Infrastruktur. WebSocket-Implementierungen sind veraltet. Symptom bei Fehlkonfiguration: Server startet, Health-Check grün, aber Client-Verbindungen schlagen fehl. Häufig übersehen, weil viele Tutorials `transport="stdio"` als …

### Remediation

```diff
- mcp.run(transport="stdio")
+ transport = os.environ.get("MCP_TRANSPORT", "stdio")
+ if transport in ("sse", "streamable-http"):
+     mcp.settings.host = os.environ.get("MCP_HOST", "0.0.0.0")
+     mcp.settings.port = int(os.environ.get("MCP_PORT", "8000"))
+ mcp.run(transport=transport)
```

Plus Deployment-Config (Railway):

```toml
[deploy.environment]
MCP_TRANSPORT = "streamable-http"
MCP_HOST = "0.0.0.0"
MCP_PORT = "8000"
```

### Effort Estimate

S — < 1 Tag.


### SCALE-004

## Finding: SCALE-004 — Containerization mit Multi-Stage-Builds

**Severity:** medium
**Status:** Open
**Server:** fedlex-mcp
**Check-Reference:** SCALE-004
**PDF-Reference:** Sec 5.3
**Verifikations-Status:** fail

### Observed Behavior

- Cloud-deployed (Render), aber kein Dockerfile im Repo

### Gaps / Abweichung vom Standard

- Keine Multi-Stage-Containerisierung
- Kein non-root USER, kein HEALTHCHECK

### Risk Description

Container-Images für MCP-Server sind oft 800 MB – 1.5 GB gross, weil Build-Toolchains (gcc, Rust, npm-build-deps) im finalen Image bleiben. Multi-Stage-Builds trennen Build und Runtime: das finale Image enthält nur den fertigen Server plus minimale Runtime-Dependencies (typischerweise 80–150 MB). Vorteile über Image-Grösse hinaus: kleinere Angriffsfläche (kein gcc, kein curl, keine Test-Tools im Production-Image), schnellere Pull-Zeiten (relevant bei Auto-Scaling), weniger CVE-Treffer im Container-Scan.

### Remediation

```diff
- FROM python:3.11
- WORKDIR /app
- COPY . .
- RUN pip install -e .
- CMD ["python", "-m", "server"]
+ FROM python:3.11-slim AS builder
+ WORKDIR /build
+ COPY pyproject.toml .
+ COPY src/ ./src/
+ RUN pip install --no-cache-dir --user -e .
+
+ FROM python:3.11-slim AS runtime
+ COPY --from=builder /root/.local /root/.local
+ COPY src/ /app/src/
+ WORKDIR /app
+ ENV PATH=/root/.local/bin:$PATH PYTHONUNBUFFERED=1
+ USER nobody
+ HEALTHCHECK CMD curl -f http://localhost:8000/healthz || exit 1
+ CMD ["python", "-m", "server"]
```

### Effort Estimate

S — < 1 Tag.


### SDK-001

## Finding: SDK-001 — FastMCP Lifespan via @asynccontextmanager + AsyncExitStack

**Severity:** high
**Status:** Open
**Server:** fedlex-mcp
**Check-Reference:** SDK-001
**PDF-Reference:** Sec 3.1
**Verifikations-Status:** fail

### Observed Behavior

- run_sparql erstellt httpx.AsyncClient pro Tool-Call (server.py:89)

### Gaps / Abweichung vom Standard

- Verletzt explizit 'Keine httpx.AsyncClient() pro Tool-Call'
- Keine @asynccontextmanager-lifespan, kein geteilter Client/Connection-Pool

### Risk Description

MCP-Server halten häufig Ressourcen, die über die einzelne Tool-Anfrage hinaus existieren: HTTP-Connection-Pools, DB-Pools, Redis-Verbindungen, gecachte Auth-Tokens, Pre-Computed-Indexes. Werden diese pro Tool-Call neu erzeugt, bricht die Performance ein. Werden sie gar nicht aufgeräumt, ergeben sich Resource-Leaks (offene TCP-Connections, dangling Cursor). FastMCP bietet das Lifespan-Pattern dafür: Eine `@asynccontextmanager`-Funktion erhält den FastMCP-Server, initialisiert Ressourcen vor dem ersten Request und räumt sie nach dem letzten Request sauber ab. Im Multi-Server-Setup (mehrere …

### Remediation

Migrationsweg:

```diff
+ from contextlib import asynccontextmanager
+ import httpx
+
+ @asynccontextmanager
+ async def lifespan(server):
+     server.state.http = httpx.AsyncClient(timeout=30)
+     try:
+         yield
+     finally:
+         await server.state.http.aclose()
+
- mcp = FastMCP("zurich-opendata")
+ mcp = FastMCP("zurich-opendata", lifespan=lifespan)

  @mcp.tool()
- async def search(query: str):
-     async with httpx.AsyncClient() as client:
-         return (await client.get(f"https://api/{query}")).json()
+ async def search(query: str, ctx):
+     return (await ctx.fastmcp.state.http.get(f"https://api/{query}")).json()
```

### Effort Estimate

S — < 1 Tag. Lifespan-Block + Tool-Refactoring + Tests.


### SDK-002

## Finding: SDK-002 — Pydantic v2 / TypedDict / Dataclass als Tool-Returns

**Severity:** medium
**Status:** Open
**Server:** fedlex-mcp
**Check-Reference:** SDK-002
**PDF-Reference:** Sec 3.1
**Verifikations-Status:** partial

### Observed Behavior

- Pydantic v2 als Input-Modelle mit Field-Constraints (server.py:149-217)

### Gaps / Abweichung vom Standard

- Tool-Returns sind -> str (Markdown), kein strukturierter Envelope mit source/provenance/results/count
- Keine Literal-Types fuer enumerable Status

### Risk Description

FastMCP wraps Tool-Returns automatisch in MCP-konformes Format — aber nur, wenn der Return-Typ strukturiert ist. Bei plain `dict` oder `str` muss FastMCP raten, welche Felder optional sind, welche Validierungen gelten, was passiert wenn Schema-Mismatches auftreten. Bei Pydantic-`BaseModel`, `TypedDict` oder `@dataclass` ist alles explizit und typgeprüft. Konkrete Vorteile: 1. **Automatische Schema-Generierung:** FastMCP exponiert das Output-Schema im `tools/list`-Manifest. Das LLM weiss damit, was es erwarten kann, und kann Folge-Calls präziser planen. 2. **Runtime-Validation:** Wenn der …

### Remediation

```diff
+ from pydantic import BaseModel, Field
+ from typing import Literal
+
+ class SearchResponse(BaseModel):
+     source: str = Field(default="DataSource Name — CC BY 4.0")
+     provenance: Literal["live_api", "cached", "weekly_dump"]
+     results: list[dict]
+     count: int

  @mcp.tool()
- async def search(query: str):
-     results = await api.search(query)
-     return {"results": results, "count": len(results)}
+ async def search(query: str, ctx) -> SearchResponse:
+     results = await api.search(query)
+     return SearchResponse(
+         provenance="live_api",
+         results=results,
+         count=len(results),
+     )
```

### Effort Estimate

S — < 1 Tag. Pro Tool 5–15 Minuten Refactoring + Tests.


### SDK-003

## Finding: SDK-003 — Context Injection für Progress Reports und Logging

**Severity:** medium
**Status:** Open
**Server:** fedlex-mcp
**Check-Reference:** SDK-003
**PDF-Reference:** Sec 3.1
**Verifikations-Status:** partial

### Observed Behavior

- Tools nutzen async/await korrekt

### Gaps / Abweichung vom Standard

- Kein ctx: Context-Parameter in irgendeinem Tool
- SPARQL-Calls bis 45s Timeout ohne ctx.report_progress
- Kein ctx.info/ctx.warning

### Risk Description

FastMCP bietet via `Context`-Parameter ein typsicheres Interface zu Server-Internals: Logging, Progress-Reports, Client-Info, Session-State, Sampling, Elicitation. Tools, die `ctx: Context` als Parameter deklarieren, bekommen dieses Objekt automatisch injiziert (Dependency Injection durch FastMCP). **Relevante Anwendungen:** - **Progress-Reports:** Bei lang laufenden Tools (>2s) sollte der Client Fortschritts-Events sehen — sonst Timeout oder UX-Bruch. - **Strukturiertes Logging:** `ctx.info()`, `ctx.debug()`, `ctx.warning()` werden über das MCP-Protokoll an den Client weitergeleitet …

### Remediation

Migrationsweg für ein langes Tool:

```diff
+ from mcp.server.fastmcp import Context

  @mcp.tool()
- async def export_all_records(format: str) -> dict:
-     records = await db.fetch_all()
-     for record in records:
-         await transform(record, format)
-     return {"count": len(records)}
+ async def export_all_records(format: str, ctx: Context) -> dict:
+     await ctx.info(f"Starting export in format={format}")
+     records = await db.fetch_all()
+     await ctx.info(f"Loaded {len(records)} records, transforming...")
+
+     transformed = []
+     for i, record in enumerate(records):
+         if i % 50 == 0:
+             await ctx.report_progress(
+                 progress=i,
+                 total=len(records),
+                 message=f"Transformed {i}/{len(records)}",
+             )
+         transformed.append(await transform(record, format))
+
+     await ctx.info(f"Export complete: {len(transformed)} records")
+     return {"count": len(transformed), "format": format}
```

### Effort Estimate

S — < 1 Tag. Pro Tool 10 Minuten + Tests.


### SDK-004

## Finding: SDK-004 — CORS Mcp-Session-Id Exposure bei HTTP/SSE

**Severity:** high
**Status:** Open
**Server:** fedlex-mcp
**Check-Reference:** SDK-004
**PDF-Reference:** Sec 3.1
**Verifikations-Status:** fail

### Observed Behavior

- Dual/HTTP-Transport aktiv (streamable-http)

### Gaps / Abweichung vom Standard

- Keine CORS-Middleware konfiguriert
- Mcp-Session-Id nicht via expose_headers/allow_headers exponiert -> Browser/Cloud-Connector-Zugriff bricht

### Risk Description

Bei Streamable HTTP / SSE läuft die MCP-Kommunikation über Cross-Origin-Requests, wenn der Client (Browser-basiert) auf einer anderen Domain als der Server hostet. Der Server gibt nach `init` einen `Mcp-Session-Id`-Header in der Response zurück — diesen muss der Browser an Folge-Requests anhängen können. Das Problem: Browser blockieren standardmässig den Zugriff auf Custom-Response-Headers via JavaScript (CORS-Spezifikation). Damit der Client den `Mcp-Session-Id`-Header lesen kann, muss der Server ihn explizit über `Access-Control-Expose-Headers: Mcp-Session-Id` freigeben. Wird dieser Header …

### Remediation

```diff
  from starlette.applications import Starlette
  from starlette.routing import Mount
+ from starlette.middleware import Middleware
+ from starlette.middleware.cors import CORSMiddleware

+ ALLOWED_ORIGINS = [
+     o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()
+ ]
+
+ middleware = [
+     Middleware(
+         CORSMiddleware,
+         allow_origins=ALLOWED_ORIGINS,
+         allow_methods=["GET", "POST", "OPTIONS"],
+         allow_headers=["Content-Type", "Mcp-Session-Id", "Authorization"],
+         expose_headers=["Mcp-Session-Id"],
+         allow_credentials=True,
+     ),
+ ]
+
  app = Starlette(
      routes=[Mount("/", app=mcp.streamable_http_app())],
+     middleware=middleware,
  )
```

Plus Umgebungsvariable:

```bash
# .env (production)
ALLOWED_ORIGINS=https://app.schulamt.zh.ch,https://claude.ai
```

### Effort Estimate

S — < 1 Tag. Middleware-Konfig + ENV-Var + Browser-Test.


### SEC-004

## Finding: SEC-004 — SSRF-Prevention: HTTPS-Enforcement + IP-Blocklisting

**Severity:** critical
**Status:** Open
**Server:** fedlex-mcp
**Check-Reference:** SEC-004
**PDF-Reference:** Sec 4.4
**Verifikations-Status:** partial

### Observed Behavior

- Ausgehender Endpoint ist fixe HTTPS-Konstante SPARQL_ENDPOINT (server.py:39); User-Input bildet NIE die URL -> SSRF nicht ausnutzbar

### Gaps / Abweichung vom Standard

- Keine explizite HTTPS/IP-Blocklist-Validierung
- WICHTIGER: keywords/sr_number werden ungeescaped per f-string in SPARQL-Query interpoliert (z.B. server.py:270-272) -> SPARQL-Injection-Vektor (ein " bricht aus dem FILTER aus); Impact gering (read-only, oeffentliche Daten), aber Korrektheits-/Robustheitsrisiko

### Risk Description

Server-Side Request Forgery (SSRF) entsteht, wenn ein MCP-Server URLs aus User-Input (oder LLM-generierten Args) direkt an HTTP-Clients weitergibt. Ein Angreifer kann den Server dann zwingen, beliebige interne Adressen abzurufen — insbesondere die Cloud-Metadata-Endpunkte. **Kritische Targets:** | Target | IP/Range | Risiko | |---|---|---| | AWS IMDS | `169.254.169.254` | EC2-Credentials, IAM-Rollen-Token | | GCP Metadata | `169.254.169.254` (Header `Metadata-Flavor: Google`) | Service-Account-Token | | Azure IMDS | `169.254.169.254` (Header `Metadata: true`) | Managed-Identity-Token | | …

### Remediation

Volles Pattern oben. Zusätzlich für Defense-in-Depth:

### Container-Level Egress-Filtering

```yaml
# Kubernetes NetworkPolicy
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: mcp-server-egress
spec:
  podSelector:
    matchLabels:
      app: mcp-server
  policyTypes:
    - Egress
  egress:
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0
            except:
              - 10.0.0.0/8
              - 172.16.0.0/12
              - 192.168.0.0/16
              - 169.254.0.0/16
              - 127.0.0.0/8
      ports:
        - protocol: TCP
          port: 443
```

### IMDSv2 statt IMDSv1 (AWS-spezifisch)

Falls auf AWS deployed: IMDSv2 mit Hop-Limit 1 erzwingen (verhindert SSRF auch bei Code-Bug).

```bash
aws ec2 modify-instance-metadata-options \
  --instance-id i-xxx \
  --http-tokens required \
  --http-put-response-hop-limit 1
```

### Effort Estimate

M — 1–3 Tage. Egress-Proxy-Setup + URL-Validation-Layer + Tests.


### SEC-005

## Finding: SEC-005 — DNS-Rebinding-Prevention: DNS-Pinning gegen TOCTOU

**Severity:** high
**Status:** Open
**Server:** fedlex-mcp
**Check-Reference:** SEC-005
**PDF-Reference:** Sec 4.4
**Verifikations-Status:** partial

### Observed Behavior

- Fixer, vertrauenswuerdiger Gov-Endpoint -> DNS-Rebinding-Risiko vernachlaessigbar

### Gaps / Abweichung vom Standard

- Kein explizites DNS-Pinning (eine Resolution pro Request)

### Risk Description

SEC-004 (SSRF-Prevention) verlangt: Resolved IP wird gegen Blocklist geprüft, dann Request mit dieser IP. DNS-Rebinding ist ein verfeinerter Angriff, der diese Defense umgeht — durch zwei verschiedene DNS-Antworten für denselben Hostnamen mit kurzem TTL: **Ablauf des Angriffs (TOCTOU = Time-Of-Check-Time-Of-Use):** 1. Angreifer kontrolliert `evil.attacker.com` mit DNS-TTL = 1 Sekunde 2. Erste Auflösung: `evil.attacker.com` → `198.51.100.42` (öffentliche IP, passiert SSRF-Check) 3. Server validiert: IP ist nicht in Blocklist → Pass 4. Server macht zweiten DNS-Lookup für eigentlichen Request …

### Remediation

### Schritt 1: HTTP-Client mit Custom Transport

```python
import httpx
import socket
import ipaddress

class PinnedTransport(httpx.AsyncHTTPTransport):
    """HTTPX Transport mit DNS-Pinning."""

    async def handle_async_request(self, request):
        url = request.url
        if url.scheme != "https":
            raise httpx.RequestError("Only HTTPS allowed")

        # Resolve einmalig
        loop = asyncio.get_event_loop()
        addrinfo = await loop.getaddrinfo(
            url.host, url.port, type=socket.SOCK_STREAM
        )
        resolved_ip = addrinfo[0][4][0]

        # Range-Check
        ip = ipaddress.ip_address(resolved_ip)
        for blocked in BLOCKED_NETWORKS:
            if ip in blocked:
                raise httpx.RequestError(f"Blocked IP: {ip}")

        # URL mit gepinnter IP, aber Host-Header bleibt
        pinned_url = httpx.URL(str(url).replace(url.host, resolved_ip, 1))
        new_request = httpx.Request(
            method=request.method,
            url=pinned_url,
            headers=httpx.Headers(request.headers),
            content=request.content,
            extensions=request.extensions,
        )
        new_request.headers["Host"] = url.host
        # SNI bleibt durch URL-Hostname (httpx interner default)
        return await super().handle_async_request(new_request)


# Verwendung
async with httpx.AsyncClient(transport=PinnedTransport()) as client:
    response = await client.get("https://api.external.com/data")
```

### Schritt 2: Alternative — Egress-Proxy

Wenn Custom-Transport zu komplex: Stripe Smokescreen als Sidecar erledigt DNS-Pinning automatisch.

```yaml
# docker-compose.yml
services:
  smokescreen:
    image: stripe/smokescreen:latest
    command: ["--listen-ip", "127.0.0.1", "--listen-port", "4750"]

  mcp-server:
    image: malkreide/mcp-server
    environment:
      HTTPS_PROXY: http://smokescreen:4750
```

```python
# Im Code: einfach Proxy nutzen
async with httpx.AsyncClient(proxy="http://localhost:4750") as client:
    return await client.get(url)
```

### Schritt 3: Tests

Wie im Mock-Beispiel oben. Plus Integration-Test, der nachweist dass die SSRF-Test-Suite (SEC-004 Modus 3) auch mit Rebinding-Versuchen besteht.

### Effort Estimate

M — 1–3 Tage. Custom-Transport oder Egress-Proxy-Setup + Tests.


### SEC-018

## Finding: SEC-018 — Input-Validation an Tool-Boundaries (Pydantic strict / Zod)

**Severity:** high
**Status:** Open
**Server:** fedlex-mcp
**Check-Reference:** SEC-018
**PDF-Reference:** Sec 3 / Sec 4 (Defense-in-Depth)
**Verifikations-Status:** partial

### Observed Behavior

- Alle Tool-Args via Pydantic mit min/max_length, ge/le, extra=forbid (server.py:149-217)

### Gaps / Abweichung vom Standard

- strict=True nicht gesetzt
- keywords/sr_number ohne pattern-Whitelist -> fliessen ungeescaped in SPARQL (siehe SEC-004)

### Risk Description

Tool-Argumente kommen vom LLM — einer probabilistischen Quelle, die halluzinieren, formattieren-falsch oder von Prompt-Injection beeinflusst sein kann. Ohne strikte Input-Validation am Tool-Boundary werden invalide oder bösartige Inputs in die Geschäftslogik weitergereicht und können dort: 1. **Unerwartete Exceptions** auslösen → Error-Pfad könnte Information leaken (siehe OBS-002) 2. **Type Confusion** triggern → z.B. `user_id: int` aber LLM schickt String → SQL-Coercion-Bug 3. **Range-Violations** verursachen → z.B. negative Pagination-Limits → DB-Crash oder Memory-Explosion 4. …

### Remediation

### Schritt 1: Schema pro Tool extrahieren

```diff
+ from typing import Annotated
+ from pydantic import BaseModel, Field, StringConstraints
+
+ class SearchArgs(BaseModel):
+     model_config = {"strict": True, "extra": "forbid"}
+     query: Annotated[str, StringConstraints(min_length=2, max_length=200)]
+     limit: Annotated[int, Field(ge=1, le=100)] = 10

  @mcp.tool()
- async def search(query: str, limit: int = 10) -> dict:
+ async def search(args: SearchArgs, ctx: Context) -> dict:
-     return await db.search(query, limit=limit)
+     return await db.search(args.query, limit=args.limit)
```

### Schritt 2: ValidationError sauber behandeln

```python
from pydantic import ValidationError

@mcp.tool()
async def search(args: SearchArgs, ctx: Context) -> dict:
    try:
        # Pydantic validiert beim Parsing automatisch — kein Aufruf nötig
        # Falls manuell aus dict gebaut: SearchArgs.model_validate(raw_dict)
        return await db.search(args.query, limit=args.limit)
    except ValidationError as e:
        # Wird normal nicht erreicht (FastMCP fängt das ab),
        # aber Defense-in-Depth:
        return {
            "isError": True,
            "content": [TextContent(
                type="text",
                text=f"Invalid arguments: {e.errors()[0]['msg']}"
            )],
        }
```

### Schritt 3: Tests gegen Edge-Cases

```python
@pytest.mark.parametrize("invalid_args,expected_error", [
    ({"query": "a", "limit": 10}, "min_length"),       # zu kurz
    ({"query": "x"*500, "limit": 10}, "max_length"),   # zu lang
    ({"query": "test", "limit": 0}, "greater_than_or_equal"),
    ({"query": "test", "limit": 99999}, "less_than_or_equal"),
    ({"query": "test", "limit": 10, "evil": "field"}, "extra_forbidden"),
])
async def test_search_rejects_invalid(invalid_args, expected_error):
    with pytest.raises(ValidationError) as exc:
        SearchArgs.model_validate(invalid_args)
    assert any(expected_error in err["type"] for err in exc.value.errors())
```

### Effort Estimate

S — < 1 Tag pro Server bei wenigen Tools, M bei vielen Tools (10+).


### SEC-021

## Finding: SEC-021 — Egress-Allow-List: Code-Layer und Network-Layer

**Severity:** high
**Status:** Open
**Server:** fedlex-mcp
**Check-Reference:** SEC-021
**PDF-Reference:** Anhang B5 + B12
**Verifikations-Status:** partial

### Observed Behavior

- De-facto Egress auf genau einen fixen Host (fedlex.data.admin.ch)

### Gaps / Abweichung vom Standard

- Keine explizite frozenset-Allow-List im Code
- Keine Network-Layer-Egress-Policy / docs/network-egress.md

### Risk Description

SEC-004 (SSRF-Prevention) blockiert Requests an interne IP-Ranges. SEC-021 ergänzt das auf der **anderen Seite**: welche externen Ziele darf der Server überhaupt erreichen? Defense-in-Depth verlangt zwei Layer: **1. Code-Layer Allow-List:** Im Server-Code wird vor jedem ausgehenden HTTP-Request geprüft, ob die Ziel-Domain in einer expliziten Allow-Liste steht. Verhindert versehentliche oder durch Prompt-Injection getriggerte Kontakte zu nicht-autorisierten Domains. **2. Network-Layer Egress Control:** Auf Cloud-Ebene (AWS Security Groups, Azure NSG, Cloudflare WARP, Kubernetes …

### Remediation

### Schritt 1: Allow-List-Inventar

Pro Server alle ausgehenden HTTP-Hosts identifizieren:

```bash
grep -rE 'https://[a-z0-9.-]+' src/ | \
  sed -E 's/.*https:\/\/([a-z0-9.-]+).*/\1/' | sort -u
```

Resultat: minimale Allow-Liste.

### Schritt 2: Code-Layer einbauen

Wie Pass-Pattern Modus 1.

### Schritt 3: Network-Layer einbauen

Bei Kubernetes: NetworkPolicy wie oben. Bei AWS: Security Group mit egress-Rules. Bei Cloudflare WARP: Zero-Trust-Policy.

### Schritt 4: Tests gegen Regression

```python
async def test_egress_blocked_to_non_allowlisted_host():
    with pytest.raises(PermissionError, match="not in allow-list"):
        await fetch_external_data("https://evil.example.com/", mock_ctx())


async def test_egress_allowed_to_allowlisted_host():
    # Mock-Response, kein echter Network-Call
    with respx.mock:
        respx.get("https://opendata.swiss/api/...").respond(200, json={"ok": True})
        result = await fetch_external_data("https://opendata.swiss/api/...", mock_ctx())
        assert result["ok"]
```

### Effort Estimate

M — 1–3 Tage. Code-Layer-Allow-List + Network-Policy + Doku + Tests.


### SEC-022

## Finding: SEC-022 — Tool-Hash-Pinning + Namespace-Präfix gegen Rug Pull

**Severity:** high
**Status:** Open
**Server:** fedlex-mcp
**Check-Reference:** SEC-022
**PDF-Reference:** Anhang B4
**Verifikations-Status:** partial

### Observed Behavior

- Alle Tools mit konsistentem Namespace-Praefix fedlex_

### Gaps / Abweichung vom Standard

- Kein Tool-Definition-Hash-Snapshot bei Releases
- Praefix nicht als FrozenSet erzwungen

### Risk Description

SEC-015 deckt **Tool-Poisoning** ab — bösartige Inhalte in Tool-Beschreibungen beim Onboarding. SEC-022 ergänzt das um zwei verwandte Angriffsklassen: **Rug Pull:** Server registriert beim Onboarding harmlose Tool-Beschreibungen. User stimmt zu. Nach erfolgreicher Approval ändert der Server seine Tool-Beschreibungen — z.B. fügt versteckte Instruktionen hinzu, die der LLM beim nächsten Aufruf befolgt. Klassischer Bait-and-Switch. **Cross-Server Tool Shadowing:** Ein bösartiger Server registriert ein Tool mit demselben Namen wie ein vertrauenswürdiger Server (z.B. beide haben …

### Remediation

### Schritt 1: Namespace-Audit

Server-Identity festlegen — typisch der Repo-Name als snake_case-Präfix:

| Repo | Namespace |
|---|---|
| `zh-education-mcp` | `zh_education` |
| `zurich-opendata-mcp` | `zurich_opendata` |
| `parlament-mcp` | `parlament_ch` |

### Schritt 2: Tool-Renaming

```diff
- @mcp.tool()
- async def search(query: str): ...
+ @mcp.tool(name="zh_education__search")
+ async def search(query: str): ...
```

Bei Renaming: Major-Version-Bump, da Tool-Namen Breaking-Changes sind.

### Schritt 3: Hash-Snapshot-Workflow

CI-Step wie im Pass-Pattern Modus 2. `tool-hashes.json` als Artefakt im Release.

### Schritt 4: Bei Update-Disziplin (Synergie zu ARCH-012)

CHANGELOG-Template um «Tool Definition Changes»-Sektion erweitern:

```markdown

### Effort Estimate

M — 1–3 Tage pro Server. Namespace-Renaming + Hash-Workflow + CHANGELOG-Updates.


---

## 6. Remediation-Plan

### Empfohlene Reihenfolge

1. **ARCH-005** (critical, partial)
2. **SEC-004** (critical, partial)
3. **ARCH-004** (high, partial)
4. **OBS-001** (high, partial)
5. **OBS-002** (high, partial)
6. **OPS-001** (high, fail)
7. **OPS-003** (high, partial)
8. **SCALE-001** (high, partial)
9. **SDK-001** (high, fail)
10. **SDK-004** (high, fail)
11. **SEC-005** (high, partial)
12. **SEC-018** (high, partial)
13. **SEC-021** (high, partial)
14. **SEC-022** (high, partial)
15. **ARCH-002** (medium, partial)
16. **ARCH-003** (medium, partial)
17. **ARCH-012** (medium, partial)
18. **OBS-003** (medium, fail)
19. **OBS-006** (medium, fail)
20. **SCALE-004** (medium, fail)
21. **SDK-002** (medium, partial)
22. **SDK-003** (medium, partial)

---

## 7. Audit-Metadata

| Feld | Wert |
|---|---|
| skill_version | `1.0.0` |
| catalog_version | `68 checks / hash 091f446b` |
| policy | `fail-or-partial` |
| audit_date | `2026-06-03` |


_Generated by tools/build_report.py — do not edit by hand._
