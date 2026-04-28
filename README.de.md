[:gb: English Version](README.md)

> :switzerland: **Teil des [Swiss Public Data MCP Portfolios](https://github.com/malkreide)**

# :balance_scale: fedlex-mcp

![Version](https://img.shields.io/badge/version-0.1.0-blue)
[![Lizenz: MIT](https://img.shields.io/badge/Lizenz-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-purple)](https://modelcontextprotocol.io/)
[![Kein API-Schluessel](https://img.shields.io/badge/Auth-keiner%20erforderlich-brightgreen)](https://github.com/malkreide/fedlex-mcp)
![CI](https://github.com/malkreide/fedlex-mcp/actions/workflows/ci.yml/badge.svg)

> MCP-Server fuer das Schweizer Bundesrecht -- SR durchsuchen, Rechtsaenderungen ueberwachen, BBl und Staatsvertraege abfragen via Claude Desktop oder Claude.ai

---

## Uebersicht

`fedlex-mcp` verbindet KI-Assistenten (Claude) mit dem **Fedlex SPARQL-Endpoint** der Schweizerischen Bundeskanzlei. Damit koennen KI-Agenten direkt im Gespraech Schweizer Bundesrecht nachschlagen, Rechtsaenderungen ueberwachen und Gesetze analysieren -- ohne manuelle Recherche auf fedlex.admin.ch.

**Metapher:** USB-C fuer Bundesrecht. Einmal angeschlossen, kann Claude jederzeit in die Systematische Rechtssammlung greifen.

---

## Funktionen

- :balance_scale: **7 Tools, 2 Resources** fuer das gesamte Schweizer Bundesrecht
- :mag: **SPARQL-basiert** -- direkter Zugang zum Fedlex-Linked-Data-Endpoint
- :globe_with_meridians: **4 Sprachen** -- Deutsch, Franzoesisch, Italienisch, Raetoromanisch
- :unlock: **Kein API-Schluessel erforderlich** -- alle Daten unter offener Wiederverwendungslizenz
- :cloud: **Dualer Transport** -- stdio (Claude Desktop) + Streamable HTTP (Cloud)

---

## Voraussetzungen

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (empfohlen) oder pip

---

## Installation

```bash
# Repository klonen
git clone https://github.com/malkreide/fedlex-mcp.git
cd fedlex-mcp

# Installieren
pip install -e .
# oder mit uv:
uv pip install -e .
```

Oder mit `uvx` (ohne dauerhafte Installation):

```bash
uvx fedlex-mcp
```

---

## Schnellstart

```bash
# stdio (fuer Claude Desktop)
python -m fedlex_mcp.server

# Streamable HTTP (Port 8000)
python -m fedlex_mcp.server --http --port 8000
```

Sofort in Claude Desktop ausprobieren:

> *"Zeig mir alle gueltigen Bundesgesetze zur Berufsbildung"*
> *"Was steht im Datenschutzgesetz? Ist es noch in Kraft?"*
> *"Welche Bundesgesetze treten in den naechsten 3 Monaten in Kraft?"*

---

## Konfiguration

### Claude Desktop

Editiere `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) bzw. `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "fedlex": {
      "command": "python",
      "args": ["-m", "fedlex_mcp.server"]
    }
  }
}
```

Oder mit `uvx`:

```json
{
  "mcpServers": {
    "fedlex": {
      "command": "uvx",
      "args": ["fedlex-mcp"]
    }
  }
}
```

**Pfad zur Konfigurationsdatei:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

### Cloud-Deployment (SSE fuer Browser-Zugriff)

Fuer den Einsatz via **claude.ai im Browser** (z.B. auf verwalteten Arbeitsplaetzen ohne lokale Software-Installation):

**Render.com (empfohlen):**
1. Repository auf GitHub pushen/forken
2. Auf [render.com](https://render.com): New Web Service -> GitHub-Repo verbinden
3. Start-Befehl setzen: `python -m fedlex_mcp.server --http --port 8000`
4. In claude.ai unter Settings -> MCP Servers eintragen: `https://your-app.onrender.com/sse`

> *"stdio fuer den Entwickler-Laptop, SSE fuer den Browser."*

---

## Demo

![Demo: Claude verwendet fedlex_search_laws](docs/assets/demo.svg)

---

## Verfuegbare Tools

| Tool | Beschreibung |
|------|-------------|
| `fedlex_search_laws` | Erlasse der SR nach Stichwort im Titel suchen |
| `fedlex_get_law_by_sr` | Erlass nach SR-Nummer abrufen (z.B. `235.1` = DSG) |
| `fedlex_get_recent_publications` | Neueste Publikationen der Amtlichen Sammlung (AS) |
| `fedlex_get_upcoming_changes` | Erlasse, die bald in Kraft treten (Rechtsmonitoring) |
| `fedlex_search_gazette` | Im Bundesblatt (BBl) suchen |
| `fedlex_get_law_history` | Alle Fassungen eines Erlasses (Versionsgeschichte) |
| `fedlex_search_treaties` | Staatsvertraege (SR-Nummern beginnen mit `0.`) |

### Beispiel-Abfragen

| Abfrage | Tool |
|---------|------|
| *"Zeig mir alle gueltigen Bundesgesetze zur Berufsbildung"* | `fedlex_search_laws` |
| *"Was steht im Datenschutzgesetz?"* | `fedlex_get_law_by_sr` |
| *"Welche Gesetze treten in den naechsten 3 Monaten in Kraft?"* | `fedlex_get_upcoming_changes` |
| *"Was hat der Bundesrat diese Woche im Bundesblatt publiziert?"* | `fedlex_get_recent_publications` |
| *"Zeig mir die Versionsgeschichte des DSG"* | `fedlex_get_law_history` |
| *"Welche Bildungsabkommen hat die Schweiz mit der EU?"* | `fedlex_search_treaties` |

→ Weitere Anwendungsbeispiele nach Zielgruppe →

---

## Architektur

```
+-------------------+     +------------------------------+     +--------------------------+
|   Claude / KI     |---->|  Fedlex MCP                  |---->|  Fedlex SPARQL Endpoint  |
|   (MCP Host)      |<----|  (MCP Server)                |<----|  (Schweizerische         |
+-------------------+     |                              |     |   Bundeskanzlei)         |
                          |  7 Tools . 2 Resources       |     +--------------------------+
                          |  Stdio | SSE                 |
                          |                              |
                          |  Keine Authentifizierung     |
                          +------------------------------+
```

### Datenmodell (JOLux-Ontologie)

```
jolux:ConsolidationAbstract  <-  SR-Eintrag
  +-- jolux:isRealizedBy  ->  jolux:Expression (URI endet auf /de, /fr, /it, /rm)
     +-- jolux:title               "Bundesgesetz vom 19. Juni 1992 ueber den Datenschutz"
     +-- jolux:titleShort          "DSG"
     +-- jolux:historicalLegalId   "235.1"

jolux:inForceStatus:
  .../0  In Kraft
  .../1  Nicht mehr in der SR publiziert
  .../3  Nicht mehr in Kraft
```

**SPARQL-Endpoint:** `https://fedlex.data.admin.ch/sparqlendpoint`
**Lizenz:** Freie Wiederverwendung (kommerziell und andere Zwecke) gemaess [fedlex.admin.ch](https://www.fedlex.admin.ch/de/broadcasters)

---

## Sprachen

| Code | Sprache |
|------|---------|
| `de` | Deutsch (Standard, vollstaendigste Abdeckung) |
| `fr` | Franzoesisch |
| `it` | Italienisch |
| `rm` | Raetoromanisch |

---

## Projektstruktur

```
fedlex-mcp/
+-- src/fedlex_mcp/
|   +-- __init__.py              # Package
|   +-- server.py                # 7 Tools, 2 Resources
+-- tests/
|   +-- test_server.py           # Unit-Tests (gemockt)
+-- .github/workflows/ci.yml     # GitHub Actions (Python 3.11/3.12/3.13)
+-- pyproject.toml
+-- CHANGELOG.md
+-- CONTRIBUTING.md
+-- LICENSE
+-- README.md                    # Englische Hauptversion
+-- README.de.md                 # Diese Datei (Deutsch)
```

---

## Bekannte Einschraenkungen

- **SPARQL-Komplexitaet:** Sehr breite Stichwortsuchen koennen ein Timeout verursachen (45s)
- **Sprachabdeckung:** Deutsch hat die vollstaendigsten Daten; andere Sprachen koennen Luecken aufweisen
- **Historische Daten:** Nicht alle historischen Fassungen haben maschinenlesbare Metadaten
- **Rate Limiting:** Der Fedlex-Endpoint kann bei Hochfrequenz-Abfragen drosseln

---

## Tests

```bash
# Unit-Tests (kein API-Key erforderlich)
PYTHONPATH=src pytest tests/ -m "not live"

# Integrationstests (Live-API-Aufrufe)
pytest tests/ -m "live"
```

---

## Sicherheit & Grenzen

- **Read-only:** Alle Tools fuhren ausschliesslich SPARQL SELECT-Abfragen durch -- kein Schreiben, Aendern oder Loeschen von Daten am Fedlex-Endpoint.
- **Keine Personendaten:** Fedlex enthaelt oeffentliche Rechtstexte und amtliche Bekanntmachungen. Kein personenbezogener Daten (PII) werden durch diesen Server verarbeitet oder gespeichert.
- **Rate Limits:** Der Fedlex SPARQL-Endpoint ist ein oeffentlicher Dienst ohne dokumentiertes Rate Limit; verwende den `limit`-Parameter zurueckhaltend. Der Server erzwingt ein 45s-Timeout pro Anfrage.
- **Datensaktualitaet:** Die Ergebnisse spiegeln den Fedlex-Endpoint zum Abfragezeitpunkt wider. Kein Caching wird durch diesen Server durchgefuehrt.
- **Nutzungsbedingungen:** Die Daten unterliegen den Wiederverwendungsbedingungen von [fedlex.admin.ch](https://www.fedlex.admin.ch/de/broadcasters) -- freie Wiederverwendung fuer kommerzielle und andere Zwecke.
- **Keine Gewaehr:** Dieser Server ist ein Community-Projekt, nicht verbunden mit der Schweizerischen Bundeskanzlei. Die Verfuegbarkeit haengt vom vorgelagerten SPARQL-Endpoint ab.

---

## Changelog

Siehe [CHANGELOG.md](CHANGELOG.md)

---

## Mitwirken

Siehe [CONTRIBUTING.md](CONTRIBUTING.md)

---

## Lizenz

MIT-Lizenz -- siehe [LICENSE](LICENSE)

---

## Autor

Hayal Oezkan . [malkreide](https://github.com/malkreide)

---

## Credits & Verwandte Projekte

- **Fedlex:** [fedlex.admin.ch](https://www.fedlex.admin.ch/) -- Schweizerische Bundeskanzlei
- **Protokoll:** [Model Context Protocol](https://modelcontextprotocol.io/) -- Anthropic / Linux Foundation
- **Verwandt:** [swiss-cultural-heritage-mcp](https://github.com/malkreide/swiss-cultural-heritage-mcp) -- Schweizer Kulturerbe
- **Verwandt:** [zurich-opendata-mcp](https://github.com/malkreide/zurich-opendata-mcp) -- Open Data der Stadt Zuerich
- **Verwandt:** [swiss-transport-mcp](https://github.com/malkreide/swiss-transport-mcp) -- Oeffentlicher Verkehr CH
- **Portfolio:** [Swiss Public Data MCP Portfolio](https://github.com/malkreide)
