> :switzerland: **Part of the [Swiss Public Data MCP Portfolio](https://github.com/malkreide)**

# :balance_scale: fedlex-mcp

![Version](https://img.shields.io/badge/version-0.1.0-blue)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-purple)](https://modelcontextprotocol.io/)
[![No Auth Required](https://img.shields.io/badge/auth-none%20required-brightgreen)](https://github.com/malkreide/fedlex-mcp)
![CI](https://github.com/malkreide/fedlex-mcp/actions/workflows/ci.yml/badge.svg)

> MCP Server for Swiss federal law — search the SR, monitor legal changes, and query BBl/treaties via Claude Desktop or Claude.ai

[:de: Deutsche Version](README.de.md)

---

## Overview

`fedlex-mcp` connects AI assistants (Claude) with the **Fedlex SPARQL endpoint** of the Swiss Federal Chancellery. This enables AI agents to look up Swiss federal law, monitor legal changes, and analyse legislation directly in conversation — without manual research on fedlex.admin.ch.

**Metaphor:** USB-C for federal law. Once connected, Claude can reach into the Systematic Compilation at any time.

---

## Features

- :balance_scale: **7 tools, 2 resources** covering the full breadth of Swiss federal law
- :mag: **SPARQL-powered** — direct access to the Fedlex linked data endpoint
- :globe_with_meridians: **4 languages** — German, French, Italian, Romansh
- :unlock: **No API key required** — all data under open reuse licence
- :cloud: **Dual transport** — stdio (Claude Desktop) + Streamable HTTP (cloud)

---

## Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

---

## Installation

```bash
# Clone the repository
git clone https://github.com/malkreide/fedlex-mcp.git
cd fedlex-mcp

# Install
pip install -e .
# or with uv:
uv pip install -e .
```

Or with `uvx` (no permanent installation):

```bash
uvx fedlex-mcp
```

---

## Quickstart

```bash
# stdio (for Claude Desktop)
python -m fedlex_mcp.server

# Streamable HTTP (port 8000)
python -m fedlex_mcp.server --http --port 8000
```

Try it immediately in Claude Desktop:

> *"Show me all valid federal laws on vocational training"*
> *"What does the Data Protection Act say? Is it still in force?"*
> *"Which federal laws enter into force in the next 3 months?"*

---

## Configuration

### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

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

Or with `uvx`:

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

**Config file locations:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

### Cloud Deployment (SSE for browser access)

For use via **claude.ai in the browser** (e.g. on managed workstations without local software):

**Render.com (recommended):**
1. Push/fork the repository to GitHub
2. On [render.com](https://render.com): New Web Service -> connect GitHub repo
3. Set start command: `python -m fedlex_mcp.server --http --port 8000`
4. In claude.ai under Settings -> MCP Servers, add: `https://your-app.onrender.com/sse`

> *"stdio for the developer laptop, SSE for the browser."*

---

## Demo

![Demo: Claude using fedlex_search_laws](docs/assets/demo.svg)

---

## Available Tools

| Tool | Description |
|------|-------------|
| `fedlex_search_laws` | Search the Systematic Compilation (SR) by keyword in title |
| `fedlex_get_law_by_sr` | Get a law by its SR number (e.g. `235.1` = Data Protection Act) |
| `fedlex_get_recent_publications` | Latest publications from the Official Compilation (AS) |
| `fedlex_get_upcoming_changes` | Laws entering into force soon (legal monitoring) |
| `fedlex_search_gazette` | Search the Federal Gazette (BBl) |
| `fedlex_get_law_history` | All versions of a law (version history) |
| `fedlex_search_treaties` | International treaties (SR numbers starting with `0.`) |

### Example Use Cases

| Query | Tool |
|-------|------|
| *"Show me all valid federal laws on vocational training"* | `fedlex_search_laws` |
| *"What does the Data Protection Act say?"* | `fedlex_get_law_by_sr` |
| *"Which laws enter into force in the next 3 months?"* | `fedlex_get_upcoming_changes` |
| *"What did the Federal Council publish this week?"* | `fedlex_get_recent_publications` |
| *"Show me the version history of the DSG"* | `fedlex_get_law_history` |
| *"Which education treaties does Switzerland have with the EU?"* | `fedlex_search_treaties` |

→ More use cases by audience →

---

## Architecture

```
+-------------------+     +------------------------------+     +--------------------------+
|   Claude / AI     |---->|  Fedlex MCP                  |---->|  Fedlex SPARQL Endpoint  |
|   (MCP Host)      |<----|  (MCP Server)                |<----|  (Swiss Federal          |
+-------------------+     |                              |     |   Chancellery)           |
                          |  7 Tools . 2 Resources       |     +--------------------------+
                          |  Stdio | SSE                 |
                          |                              |
                          |  No authentication required  |
                          +------------------------------+
```

### Data Model (JOLux Ontology)

```
jolux:ConsolidationAbstract  <-  SR entry
  +-- jolux:isRealizedBy  ->  jolux:Expression (URI ends in /de, /fr, /it, /rm)
     +-- jolux:title               "Federal Act of 19 June 1992 on Data Protection"
     +-- jolux:titleShort          "DSG"
     +-- jolux:historicalLegalId   "235.1"

jolux:inForceStatus:
  .../0  In force
  .../1  No longer published in the SR
  .../3  No longer in force
```

**SPARQL Endpoint:** `https://fedlex.data.admin.ch/sparqlendpoint`
**Licence:** Free reuse (commercial and other purposes) per [fedlex.admin.ch](https://www.fedlex.admin.ch/de/broadcasters)

---

## Languages

| Code | Language |
|------|----------|
| `de` | German (default, most complete coverage) |
| `fr` | French |
| `it` | Italian |
| `rm` | Romansh |

---

## Project Structure

```
fedlex-mcp/
+-- src/fedlex_mcp/
|   +-- __init__.py              # Package
|   +-- server.py                # 7 tools, 2 resources
+-- tests/
|   +-- test_server.py           # Unit tests (mocked)
+-- .github/workflows/ci.yml     # GitHub Actions (Python 3.11/3.12/3.13)
+-- pyproject.toml
+-- CHANGELOG.md
+-- CONTRIBUTING.md
+-- LICENSE
+-- README.md                    # This file (English)
+-- README.de.md                 # German version
```

---

## Known Limitations

- **SPARQL complexity:** Very broad keyword searches may time out (45s timeout)
- **Language coverage:** German has the most complete data; other languages may have gaps
- **Historical data:** Not all historical versions of laws have machine-readable metadata
- **Rate limiting:** The Fedlex endpoint may throttle high-frequency requests

---

## Testing

```bash
# Unit tests (no API key required)
PYTHONPATH=src pytest tests/ -m "not live"

# Integration tests (live API calls)
pytest tests/ -m "live"
```

---

## Safety & Limits

- **Read-only:** All tools perform SPARQL SELECT queries only — no data is written, modified, or deleted on the Fedlex endpoint.
- **No personal data:** Fedlex contains public law texts and official gazettes. No personally identifiable information (PII) is processed or stored by this server.
- **Rate limits:** The Fedlex SPARQL endpoint is a public service without a documented rate limit; use `limit` parameters conservatively. The server enforces a 45s timeout per request.
- **Data freshness:** Results reflect the Fedlex endpoint at query time. No caching is performed by this server.
- **Terms of service:** Data is subject to the reuse conditions of [fedlex.admin.ch](https://www.fedlex.admin.ch/de/broadcasters) — free reuse for commercial and other purposes.
- **No guarantees:** This server is a community project, not affiliated with the Swiss Federal Chancellery. Availability depends on the upstream SPARQL endpoint.

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md)

---

## License

MIT License — see [LICENSE](LICENSE)

---

## Author

Hayal Oezkan . [malkreide](https://github.com/malkreide)

---

## Credits & Related Projects

- **Fedlex:** [fedlex.admin.ch](https://www.fedlex.admin.ch/) — Swiss Federal Chancellery
- **Protocol:** [Model Context Protocol](https://modelcontextprotocol.io/) — Anthropic / Linux Foundation
- **Related:** [swiss-cultural-heritage-mcp](https://github.com/malkreide/swiss-cultural-heritage-mcp) — Swiss cultural heritage data
- **Related:** [zurich-opendata-mcp](https://github.com/malkreide/zurich-opendata-mcp) — City of Zurich open data
- **Related:** [swiss-transport-mcp](https://github.com/malkreide/swiss-transport-mcp) — Swiss public transport
- **Portfolio:** [Swiss Public Data MCP Portfolio](https://github.com/malkreide)
