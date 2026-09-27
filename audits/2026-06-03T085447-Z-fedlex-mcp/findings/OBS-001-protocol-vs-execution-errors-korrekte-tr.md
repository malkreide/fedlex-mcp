## Finding: OBS-001 — Protocol vs. Execution Errors: korrekte Trennung

**Severity:** high
**Status:** Resolved (2026-09-27, malkreide/fedlex-mcp#86)
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

### Nachtrag 2026-09-27 — behoben

Behoben mit [malkreide/fedlex-mcp#86](https://github.com/malkreide/fedlex-mcp/pull/86).

- **Gap «Execution-Errors nicht als `isError: true`»:** behoben. Ein Ausfall von
  Fedlex oder LINDAS kam bis v2.0.1 als Resultat mit `isError: false` zurück; nur
  `match_type: "error"` im Envelope zeigte ihn an. Alle zwölf Tools werden jetzt
  über `@_tool(...)` registriert; der Wrapper macht aus genau diesem Fall ein
  `CallToolResult(is_error=True)`. `structuredContent` bleibt, das `outputSchema`
  und `tool-definitions.lock.json` sind unverändert. «Nichts gefunden»
  (`match_type: "none"`) trägt das Flag bewusst nicht.
- **Gap «Keine Tests für die Fehlerpfade»:** behoben. `tests/test_tool_errors.py`
  (34 Fälle) ruft jedes Tool aus `tools/list` in beiden Protokoll-Ären bei
  unerreichbaren Endpunkten auf, dazu Treffer, kein Treffer, Schemaverletzung und
  Direktaufruf. Gegenprobe: Wrapper neutralisiert → alle 24 Ausfallfälle rot.
- **Bewusst anders als die Remediation oben:** Kein `McpError(-32603)` für einen
  unerreichbaren Endpunkt. Ein Ausfall der Datenquelle ist nach Spec ein
  Ausführungsfehler, den das Modell sehen und einordnen soll, kein Protokollfehler.
- **Gemessen, nicht Teil des Fixes:** Das SDK beantwortet Schemaverletzung *und*
  unbekanntes Tool als Resultat mit `isError: true`, nicht als JSON-RPC-Fehler. Für
  die Schemaverletzung ist das seit Spec 2025-11-25 so vorgesehen. Beim unbekannten
  Tool ist es das Verhalten des SDK (`mcp` 2.2.0), das dieser Server nicht setzt.

Die Momentaufnahme oben (Observed Behavior, Gaps, Verifikations-Status) ist
der Befund vom 2026-06-03 und bleibt unverändert; ebenso `verification-results.json`
und `summary.json`. Achtung: `gen_findings.py` schreibt diese Datei neu, setzt
`Status: Open` fest ein und verwirft diesen Nachtrag — nach einem Neulauf von Hand
wiederherstellen.
