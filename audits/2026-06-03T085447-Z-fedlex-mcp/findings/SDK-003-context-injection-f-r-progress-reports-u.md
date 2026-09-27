## Finding: SDK-003 — Context Injection für Progress Reports und Logging

**Severity:** medium
**Status:** Open — Logging-Teil gegenstandslos seit 2026-09-27 (Spec 2026-07-28, SEP-2577); Progress-Teil offen
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

### Nachtrag 2026-09-27 — teilweise gegenstandslos

Zwei der drei Gaps lassen sich nicht mehr so umsetzen, wie die Remediation oben
es vorsieht; der dritte bleibt offen.

- **Gap «Kein ctx.info/ctx.warning» — gegenstandslos.** Die Logging-Capability
  ist mit Spec 2026-07-28 abgekündigt (SEP-2577). Der Server hatte `ctx.info()`
  beim Aufruf und `ctx.error()` im Fehlerpfad inzwischen eingeführt (spätestens
  mit malkreide/fedlex-mcp#29). Gemessen hat das in beiden Ären falsch gewirkt: Im Handshake bis
  2025-11-25 gingen die `notifications/message` hinaus, ohne dass `initialize`
  eine `logging`-Capability meldete. In der modernen Ära verwarf das SDK sie ohne
  `_meta`-Opt-in des Clients, und jeder Aufruf warf eine `MCPDeprecationWarning`.
  Entfernt mit [malkreide/fedlex-mcp#85](https://github.com/malkreide/fedlex-mcp/pull/85).
  Protokolliert wird jetzt beim Betreiber (structlog auf stderr, OBS-003; optional
  OpenTelemetry, OBS-006). Einen Fehlschlag sieht der Aufrufer im Resultat selbst
  (`isError: true`, siehe OBS-001). `tests/test_modern_era.py` sichert zu, dass
  kein Tool in einer der beiden Ären eine Log-Notification oder eine
  Abkündigungswarnung erzeugt.
- **Gap «Kein ctx: Context-Parameter» — gegenstandslos als eigenes Ziel.** Der
  Parameter war nur das Mittel für Logging und Progress. Mit dem Logging entfiel er
  in #85; für Progress käme er zurück.
- **Gap «SPARQL-Calls bis 45 s ohne ctx.report_progress» — offen.** Nicht umgesetzt
  und nicht gemessen. Die Abkündigung in 2026-07-28 betrifft laut SDK nur Progress
  vom Client zum Server, nicht `ctx.report_progress` vom Server zum Client. Ob ein
  Client in der modernen Ära ein `progressToken` mitschickt und die Meldungen
  ankommen, ist vor einer Umsetzung zu messen.

Die Momentaufnahme oben (Observed Behavior, Gaps, Verifikations-Status) ist
der Befund vom 2026-06-03 und bleibt unverändert; ebenso `verification-results.json`
und `summary.json`. Achtung: `gen_findings.py` schreibt diese Datei neu, setzt
`Status: Open` fest ein und verwirft diesen Nachtrag — nach einem Neulauf von Hand
wiederherstellen.
