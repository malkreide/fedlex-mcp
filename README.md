# Fedlex MCP Server

**Zugriff auf das Schweizer Bundesrecht via Claude Desktop oder Claude.ai**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-1.3+-green.svg)](https://modelcontextprotocol.io/)
[![Lizenz](https://img.shields.io/badge/Lizenz-MIT-lightgrey.svg)](LICENSE)

---

## Was ist das?

Dieser MCP-Server verbindet KI-Assistenten (Claude) mit dem **Fedlex SPARQL-Endpoint** der Schweizerischen Bundeskanzlei. Damit können KI-Agenten direkt im Gespräch Schweizer Bundesrecht nachschlagen, Rechtsänderungen überwachen und Gesetze analysieren — ohne manuelle Recherche auf fedlex.admin.ch.

**Metapher:** USB-C für Bundesrecht. Einmal angeschlossen, kann Claude jederzeit in die Systematische Rechtssammlung «greifen».

---

## Tools (7)

| Tool | Beschreibung |
|---|---|
| `fedlex_search_laws` | Erlasse der SR nach Stichwort im Titel suchen |
| `fedlex_get_law_by_sr` | Erlass nach SR-Nummer abrufen (z.B. `235.1` = DSG) |
| `fedlex_get_recent_publications` | Neueste Publikationen der Amtlichen Sammlung (AS) |
| `fedlex_get_upcoming_changes` | Erlasse, die bald in Kraft treten (Rechtsmonitoring) |
| `fedlex_search_gazette` | Im Bundesblatt (BBl) suchen |
| `fedlex_get_law_history` | Alle Fassungen eines Erlasses (Versionsgeschichte) |
| `fedlex_search_treaties` | Staatsverträge (SR-Nummern beginnen mit `0.`) |

---

## Anwendungsbeispiele

```
"Zeig mir alle gültigen Bundesgesetze zur Berufsbildung"
→ fedlex_search_laws(keywords="Berufsbildung")

"Was steht im Datenschutzgesetz? Ist es noch in Kraft?"
→ fedlex_get_law_by_sr(sr_number="235.1")

"Welche Bundesgesetze treten in den nächsten 3 Monaten in Kraft?"
→ fedlex_get_upcoming_changes(days_ahead=90)

"Was hat der Bundesrat diese Woche im Bundesblatt publiziert?"
→ fedlex_get_recent_publications(days=7)

"Zeig mir die Versionsgeschichte des DSG — wann trat die Revision in Kraft?"
→ fedlex_get_law_history(sr_number="235.1")

"Welche Bildungsabkommen hat die Schweiz mit der EU?"
→ fedlex_search_treaties(keywords="Bildung")
```

---

## Installation

### Voraussetzungen
- Python 3.11+
- `uv` oder `pip`

### Lokal (Claude Desktop)

```bash
# 1. Repository klonen
git clone https://github.com/malkreide/fedlex-mcp.git
cd fedlex-mcp

# 2. Abhängigkeiten installieren
pip install -r requirements.txt

# 3. Direkt testen
python server.py
```

### Claude Desktop Konfiguration

Datei öffnen:
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

Eintrag hinzufügen:

```json
{
  "mcpServers": {
    "fedlex": {
      "command": "python",
      "args": ["/absoluter/pfad/zu/fedlex-mcp/server.py"]
    }
  }
}
```

Mit `uvx` (empfohlen, kein manuelles Install):

```json
{
  "mcpServers": {
    "fedlex": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/malkreide/fedlex-mcp", "fedlex-mcp"]
    }
  }
}
```

Claude Desktop neu starten. Im Chat erscheinen danach 7 neue Tools (Hammer-Icon).

---

## Cloud-Deployment (Render.com / SSE)

Für Zugriff via Browser oder ohne lokale Installation:

```bash
# Server starten (SSE-Transport)
MCP_TRANSPORT=sse PORT=8000 python server.py
```

`render.yaml` Beispiel:

```yaml
services:
  - type: web
    name: fedlex-mcp
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: python server.py
    envVars:
      - key: MCP_TRANSPORT
        value: sse
      - key: PORT
        value: 10000
```

---

## Datenmodell (JOLux-Ontologie)

```
jolux:ConsolidationAbstract  ←  SR-Eintrag
  └─ jolux:isRealizedBy  →  jolux:Expression (URI endet auf /de, /fr, /it, /rm)
     ├─ jolux:title               "Bundesgesetz vom 19. Juni 1992 über den Datenschutz"
     ├─ jolux:titleShort          "DSG"
     └─ jolux:historicalLegalId   "235.1"

jolux:inForceStatus:
  .../0  ✅ In Kraft
  .../1  ⚠️ Nicht mehr in SR publiziert
  .../3  ❌ Nicht mehr in Kraft
```

**SPARQL-Endpoint:** `https://fedlex.data.admin.ch/sparqlendpoint`  
**Lizenz:** Freie Wiederverwendung (kommerziell und andere Zwecke) gemäss [fedlex.admin.ch/de/broadcasters](https://www.fedlex.admin.ch/de/broadcasters)

---

## Sprachen

| Code | Sprache |
|---|---|
| `de` | Deutsch (Standard, vollständigste Abdeckung) |
| `fr` | Français |
| `it` | Italiano |
| `rm` | Rumantsch |

---

## Sicherheitshinweise

- Dieser Server ist **read-only** — keine schreibenden Operationen
- Alle Abfragen gehen direkt an den öffentlichen Fedlex-Endpoint
- Keine API-Keys oder Authentifizierung erforderlich
- Datensouveränität: Keine Daten werden an Dritte übertragen

---

## Verwandte Projekte

- [Zurich Open Data MCP](https://github.com/malkreide/zurich-opendata-mcp) — Daten der Stadt Zürich
- [Swiss Transport MCP](https://github.com/malkreide/swiss-transport-mcp) — Öffentlicher Verkehr CH
- [Patent Research MCP](https://github.com/malkreide/patent-mcp) — EPO/IGE Patentdatenbanken

---

## Entwickelt von

Hayal Isik | Schulamt der Stadt Zürich | Mitglied KI-Fachgruppe Stadtverwaltung Zürich  
GitHub: [@malkreide](https://github.com/malkreide)

---

*English summary: MCP server providing access to Swiss federal law via the Fedlex SPARQL endpoint. 7 tools covering the Systematic Compilation (SR), Official Gazette, Federal Bulletin, version history, and international treaties. Read-only, no authentication required, dual transport (stdio + SSE).*
