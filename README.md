> :switzerland: **Part of the [Swiss Public Data MCP Portfolio](https://github.com/malkreide)**

# :balance_scale: fedlex-mcp

![Version](https://img.shields.io/badge/version-1.1.0-blue)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-purple)](https://modelcontextprotocol.io/)
[![No Auth Required](https://img.shields.io/badge/auth-none%20required-brightgreen)](https://github.com/malkreide/fedlex-mcp)
![CI](https://github.com/malkreide/fedlex-mcp/actions/workflows/ci.yml/badge.svg)

> MCP Server for Swiss federal law, consultations & official terminology — search the SR, monitor consultation deadlines, and translate terms across the national languages via Claude Desktop or Claude.ai

[:de: Deutsche Version](README.de.md)

---

## Overview

`fedlex-mcp` connects AI assistants (Claude) with three official Swiss SPARQL data sources:

1. **Federal law** via the **Fedlex SPARQL endpoint** — the Systematic Compilation (SR), Official Compilation (AS), Federal Gazette (BBl) and treaties.
2. **Consultations (Vernehmlassungen)** via the *same* Fedlex endpoint (`jolux:Consultation`) — the pre-parliamentary phase in which anyone can comment on a draft.
3. **TERMDAT**, the Federal Chancellery's terminology database, via the **LINDAS SPARQL endpoint** — official term equivalents across de/fr/it/rm/en.

All three are SPARQL-based, which is exactly why they live in one server rather than three: no new technology stack, only new queries against known patterns.

**Metaphor:** USB-C for federal law. *Fedlex tells you what you have to respond to. TERMDAT tells you what it is called in the other national languages.*

---

## Features

- :balance_scale: **12 tools, 2 resources** across federal law, consultations and terminology
- :mag: **SPARQL-powered** — two isolated endpoints (Fedlex + LINDAS), no shared failure mode
- :globe_with_meridians: **5 languages** — German, French, Italian, Romansh, plus English for terminology
- :unlock: **No API key required** — all data under open reuse licences
- :cloud: **Dual transport** — stdio (Claude Desktop) + Streamable HTTP (cloud)

---

## Anchor demo query

> *"Which education-related consultations are currently open, until when does the deadline run, which office is in charge — and what are the key technical terms in French and Italian for the response?"*

A single conversation chains three tools across two endpoints:

```
fedlex_get_open_consultations(topic="education")
   → fedlex_get_consultation(event_id="proj/2026/71/cons_1")
   → termdat_lookup_term(term="Volksschule", target_languages=["fr","it"])
```

Every open consultation carries `deadline`, `days_remaining` (computed at
request time in Europe/Zurich, `0` = deadline is today) and a **derived**
`status` — an expired consultation never shows up as running. Fedlex says
*what* you must respond to and *by when*; TERMDAT says *how to name it* in the
other national languages.

> **Use `topic="education"`, not `keyword="Volksschule"`.** Fedlex consultations
> have no subject taxonomy — filtering is free-text over the title, and the word
> "Volksschule" appears in **zero** consultation titles. The `topic` filter
> expands to a disclosed keyword union (Bildung, Schule, Berufsbildung,
> Hochschule, …) and reports exactly which terms it searched.

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
> *"Which consultations on education are open right now, and until when?"*
> *"What is 'Volksschule' called in French and Italian in official terminology?"*

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

| # | Tool | Source | Description |
|---|------|--------|-------------|
| 1 | `fedlex_search_laws` | Fedlex | Search the Systematic Compilation (SR) by keyword in title |
| 2 | `fedlex_get_law_by_sr` | Fedlex | Get a law by its SR number (e.g. `235.1` = Data Protection Act) |
| 3 | `fedlex_get_recent_publications` | Fedlex | Latest publications from the Official Compilation (AS) |
| 4 | `fedlex_get_upcoming_changes` | Fedlex | Laws entering into force soon (legal monitoring) |
| 5 | `fedlex_search_gazette` | Fedlex | Search the Federal Gazette (BBl) |
| 6 | `fedlex_get_law_history` | Fedlex | All versions of a law (version history) |
| 7 | `fedlex_search_treaties` | Fedlex | International treaties (SR numbers starting with `0.`) |
| 8 | `fedlex_get_open_consultations` | Fedlex | **Deadline monitoring** — open consultations (`eventEndDate >= today`, Europe/Zurich); each with `days_remaining` + derived `status`, sorted by shortest deadline; optional `topic`/`keyword` |
| 9 | `fedlex_search_consultations` | Fedlex | Full-text search over consultation title/description, with filters (topic, status, deadline range, office) |
| 10 | `fedlex_get_consultation` | Fedlex | Detail for one `eventId`: deadline, `days_remaining`, office, derived status, documents |
| 11 | `termdat_lookup_term` | LINDAS | Term → equivalents in de/fr/it/rm/en incl. definition |
| 12 | `termdat_get_concept` | LINDAS | Full TERMDAT entry for a URI or ID |

### Example Use Cases

| Query | Tool |
|-------|------|
| *"Show me all valid federal laws on vocational training"* | `fedlex_search_laws` |
| *"What does the Data Protection Act say?"* | `fedlex_get_law_by_sr` |
| *"Which laws enter into force in the next 3 months?"* | `fedlex_get_upcoming_changes` |
| *"Show me the version history of the DSG"* | `fedlex_get_law_history` |
| *"Which consultations on education are open, and until when?"* | `fedlex_get_open_consultations` |
| *"Find closed consultations about the language act"* | `fedlex_search_consultations` |
| *"Give me the full detail and documents for consultation proj/2026/71/cons_1"* | `fedlex_get_consultation` |
| *"What is 'Volksschule' called in French and Italian?"* | `termdat_lookup_term` |
| *"Show the full TERMDAT entry 40109"* | `termdat_get_concept` |

→ More use cases by audience →

---

## Architecture

Two isolated SPARQL endpoints behind one server. Separate httpx clients and
timeouts mean a LINDAS outage never breaks the `fedlex_*` tools, and vice versa.

```
+-------------------+     +------------------------------+     +--------------------------+
|   Claude / AI     |---->|  Fedlex MCP                  |---->|  Fedlex SPARQL Endpoint  |
|   (MCP Host)      |<----|  (MCP Server)                |<----|  fedlex.data.admin.ch    |
+-------------------+     |                              |     |  (law + consultations)   |
                          |  12 Tools . 2 Resources      |     +--------------------------+
                          |  Stdio | SSE                 |
                          |                              |     +--------------------------+
                          |  Isolated clients:           |---->|  LINDAS SPARQL Endpoint  |
                          |   - Fedlex  (law + cons.)     |<----|  lindas.admin.ch/query   |
                          |   - LINDAS  (TERMDAT)         |     |  (fch/termdat, TERMDAT)  |
                          |                              |     +--------------------------+
                          |  No authentication required  |
                          +------------------------------+
```

### Data Model

**JOLux Ontology — federal law (Fedlex)**

```
jolux:ConsolidationAbstract  <-  SR entry
  +-- jolux:isRealizedBy  ->  jolux:Expression (URI ends in /de, /fr, /it, /rm)
     +-- jolux:title               "Federal Act of 19 June 1992 on Data Protection"
     +-- jolux:titleShort          "DSG"
     +-- jolux:historicalLegalId   "235.1"

jolux:inForceStatus:  .../0 In force  ·  .../1 No longer published in SR  ·  .../3 No longer in force
```

**JOLux Ontology — consultations (Fedlex, same endpoint)**

```
jolux:Consultation
  +-- jolux:eventId                     "proj/2026/71/cons_1"
  +-- jolux:eventTitle                  multilingual (de/fr/it)
  +-- jolux:eventDescription            multilingual
  +-- jolux:consultationStatus          -> vocabulary URI (0..6, /2 = "Laufend"/running)
  +-- jolux:foreseenImpactToLegalResource  -> the legal resource it will amend (link to SR)
  +-- jolux:hasSubTask  ->  ?t
        +-- jolux:eventStartDate                      <- opened_on
        +-- jolux:eventEndDate                        <- the deadline (xsd:date, calendar day)
        +-- jolux:institutionInChargeOfTheEvent       <- lead department
        +-- jolux:institutionInChargeOfTheEventLevel2 <- lead office
        +-- jolux:opinionHasDraftRelatedDocument      <- consultation documents
```

There is **no** subject taxonomy on `jolux:Consultation` — thematic filtering is
free-text over `eventTitle` only, and `status` is derived from the deadline
(not the source status field).

**Legislative lifecycle — where consultations sit (all in this one server):**

```
  Vernehmlassung            Bundesblatt (BBl)          Systematische Sammlung (SR)
  (consultation)     ─────► (dispatch / act text) ───► (consolidated law in force)
  ────────────────         ─────────────────────      ───────────────────────────
  fedlex_get_open_          fedlex_search_gazette      fedlex_search_laws
    consultations           (eli/fga/…)                fedlex_get_law_by_sr
  fedlex_search_                                       fedlex_get_law_history
    consultations                                      (eli/cc/…)
  fedlex_get_consultation
        │  jolux:foreseenImpactToLegalResource
        └───────────────────────────────────────────► links a consultation forward
                                                       to the SR resource it amends
```

The consultation stage is the **earliest** public point of influence — the tools
above answer *what is open and until when*, before a draft reaches the Bundesblatt.

**schema.org — terminology (TERMDAT via LINDAS, graph `fch/termdat`)**

```
<concept>  = https://register.ld.admin.ch/termdat/40109      (a schema.ld.admin.ch/Term, ValidatedEntry)
  +-- schema:name         preferred name per language (de/fr/it/en; rm effectively absent)
  +-- schema:description  multilingual definition
  +-- schema:hasPart  ->  <term> = .../termdat/40109/3/de     (synonym/variant, language + position suffix)
```

**SPARQL endpoints:** `https://fedlex.data.admin.ch/sparqlendpoint` · `https://lindas.admin.ch/query`
**Licence:** Free reuse per [fedlex.admin.ch](https://www.fedlex.admin.ch/de/broadcasters); TERMDAT via LINDAS under open reuse.

---

## Architecture decision

**ARCH A — live SPARQL only**, for all three data areas, consistent with the
existing Fedlex integration (decided 2026-07-18).

Both sources are unauthenticated SPARQL endpoints with acceptable latency, so no
dump/offline fallback is needed: if the Fedlex endpoint is down the server cannot
function anyway, and adding a cache would only mask that. LINDAS is a **separate**
endpoint, and its outage must **not** degrade the `fedlex_*` tools.

**Isolation requirement:** Fedlex and LINDAS use separate httpx clients, separate
timeouts and separate error/status reporting. A LINDAS timeout cannot fail a
`fedlex_*` call and vice versa (covered by an isolation test).

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
|   +-- server.py                # 12 tools, 2 resources (Fedlex + LINDAS)
+-- tests/
|   +-- test_server.py           # Unit tests (mocked)
+-- .github/workflows/ci.yml     # GitHub Actions (Python 3.11/3.12/3.13)
+-- pyproject.toml
+-- CHANGELOG.md
+-- CONTRIBUTING.md               # Contributing guide (English)
+-- CONTRIBUTING.de.md            # Contributing guide (German)
+-- SECURITY.md                   # Security policy (English)
+-- SECURITY.de.md                # Security policy (German)
+-- LICENSE
+-- README.md                    # This file (English)
+-- README.de.md                 # German version
```

---

## Known Limitations

- **SPARQL complexity:** Very broad keyword searches may time out (45s timeout)
- **Language coverage:** German has the most complete data; other languages may have gaps
- **Historical data:** Not all historical versions of laws have machine-readable metadata
- **Rate limiting:** The endpoints may throttle high-frequency requests

### Consultations — scope and reliability (read this before relying on it)

- **Federal only. No cantonal consultations.** Fedlex holds *federal* (Bund)
  consultations. Cantonal consultations — often the more relevant ones for a
  school authority (Schulamt) — are **not** in Fedlex and **not** covered here.
  This is a hard scope boundary, not a gap to be worked around.
- **This is not a push service.** MCP is pull-based: the server answers *on
  request* which consultations are open and which expire soon. It cannot notify,
  schedule, or alert. Recurrence comes from you or an external scheduler — never
  from the server. "No open consultations" means *nothing is open right now*, not
  *nothing is coming*.
- **Thematic filtering is free-text, and imperfect.** `jolux:Consultation` has
  **no** subject/classification taxonomy (verified live 2026-07-20) — filtering
  is substring search over the title only. `topic="education"` expands to a
  disclosed keyword union and deliberately over-matches (a too-narrow filter
  would falsely reassure); expect some false positives (e.g. "Ausbildung" inside
  an unrelated title) and, for niche wording, possible false negatives. The
  response always states which terms were searched.
- **Coverage / latency:** ~2,553 consultations; the historical corpus 1960–1991
  sits with the Federal Archives, **out of scope**. Newly opened consultations
  appear with the upstream Fedlex publication latency (not real-time).
- **Deadlines end on the calendar day** in Europe/Zurich; `days_remaining` is
  computed at request time, never cached. `0` = the deadline is today.

**Live findings (verified 2026-07-20):**

| Query | Status | Records | Note |
|---|---|---|---|
| `COUNT(?s) {?s a jolux:Consultation}` | OK | **2,553** | full inventory |
| `hasSubTask` with start/end dates | OK | 2,505 of 2,553 | **48 without any deadline** |
| Open consultations (`eventEndDate >= today`) | OK | **42** | deadlines into autumn 2026 |
| `consultation-status` vocabulary | OK | 7 values | `/0`..`/6`, `/2` = running |
| Title contains "volksschule" / "lehrplan" | OK | **0 / 0** | anchor term itself finds nothing → use `topic` |
| Title contains "bildung" (single) vs `topic="education"` union | OK | 44 vs 66 | keyword union is broader |
| `REGEX(LCASE(?t), "a\|b")` alternation | **BROKEN** | 0 | silently empty on this endpoint → OR-chained `CONTAINS` instead |

- **Quirk 1 — the deadline wins over the status field.** Status `/2`
  ("Laufend"/running) and `eventEndDate` are **two independent signals**. The
  server derives `status` from the **date**: past deadline ⇒ `Abgeschlossen`,
  regardless of what the source status claims — so an expired consultation is
  never listed as running. When the two disagree the record is marked
  `status_conflict: true` and keeps the raw label in `status_source`.

### TERMDAT (LINDAS) — findings (verified 2026-07-18)

| Query | Status | Records | Note |
|---|---|---|---|
| `COUNT(DISTINCT ?s) a schema.ld:Term` in graph | OK | **77,692** | |
| Language tags on `schema:name` | OK | de/fr/it/en | `rm` effectively absent (0) |
| Search `schema:name = "Volksschule"` | OK | 1 | returns term URI `…/termdat/40109/3/de` |
| Concept URI `…/termdat/40109` | OK | – | 4 language variants + definition |

- **Quirk 2 — reality-check discrepancy (stated plainly).** The Federal
  Chancellery communicates roughly **400,000** TERMDAT entries. LINDAS contains
  **77,692**. The difference is unexplained — presumably only the validated,
  released subset is published as Linked Data. **A negative terminology hit does
  not mean the term is missing from TERMDAT; it only means it is not in the LINDAS
  subset.** Every TERMDAT response carries this note so the model draws no false
  conclusion.
- **Quirk 3 — two URI levels.** Concept URIs (`…/termdat/40109`) carry the
  preferred names and the definition; term URIs with a language/position suffix
  (`…/termdat/40109/3/de`) are synonyms/variants linked via `schema:hasPart`. The
  tools accept both forms and normalise internally to the concept ID.

---

## What this tool is **not**

- **Not a subscription or alerting service.** It does not watch, notify, e-mail,
  or remind. It answers when asked. Any recurring check is driven by you or an
  external scheduler, outside the server.
- **Not a cantonal source.** Federal (Bund) consultations only — see Known
  Limitations.
- **Not legal advice.** It returns public metadata and links to official
  documents. Deadlines and status are derived mechanically from the published
  data; verify anything decision-critical against the linked Fedlex page.

---

## Related processes across the portfolio

Swiss federal legislation runs a chain, and this server covers one part of it —
the pre-parliamentary consultation. The full chain is representable across three
MCP servers:

```
Vernehmlassung  →  Botschaft  →  Parlament  →  Referendum
(consultation)     (dispatch)    (debate)      (popular vote)
   fedlex-mcp        fedlex-mcp    parlament-mcp   swiss-democracy-mcp
```

- **Consultation (pre-parliamentary):** this server — `fedlex_*consultation*` tools.
- **Parliamentary phase:** [`parlament-mcp`](https://github.com/malkreide) — debates, motions, votes in the Federal Assembly.
- **Popular vote / referendum:** [`swiss-democracy-mcp`](https://github.com/malkreide) — federal popular votes. Consultations are a distinct, earlier stage — no overlap, but the same legislative lifecycle.

---

## Project Phase

This server is in **Phase 1 (read-only)**. All tools are annotated
`readOnlyHint: true` / `destructiveHint: false` and only ever query the public
Fedlex SPARQL endpoint — there are no write, send, or filesystem capabilities.

| Phase | Scope | Status |
|---|---|---|
| **1 — Read-only** | Query SR/AS/BBl/treaties | ✅ current |
| 2 — Write-capable | (none planned) | — |
| 3 — Multi-agent | (none planned) | — |

A transition to a later phase would require an audit re-run and the
human-in-the-loop controls described in the audit catalog before any
write-capable tool is added.

---

## MCP Protocol Version

The protocol version is negotiated at the `initialize` handshake by the
[`mcp`](https://pypi.org/project/mcp/) Python SDK (pinned to `>=1.3.0` in
`pyproject.toml`). The SDK is kept current via monthly Dependabot PRs
(`.github/dependabot.yml`); protocol-relevant bumps are noted in
[`CHANGELOG.md`](CHANGELOG.md).

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

- **Read-only:** All tools perform SPARQL SELECT queries only — no data is written, modified, or deleted on either endpoint. All 12 tools are annotated `readOnlyHint: true` / `destructiveHint: false` / `idempotentHint: true`.
- **No personal data:** Fedlex holds public law, gazettes and consultation metadata; TERMDAT holds official terminology. No personally identifiable information (PII) is processed or stored by this server.
- **Rate limits:** The Fedlex and LINDAS SPARQL endpoints are public services without a documented rate limit; use `limit` parameters conservatively (default 20, max 100). The server enforces a 45s timeout per request per endpoint and retries only transient failures.
- **Endpoint isolation:** Fedlex and LINDAS use separate clients and timeouts — a LINDAS outage does not affect the `fedlex_*` tools.
- **Data freshness:** Results reflect the endpoints at query time. No caching is performed by this server.
- **Terms of service:** Data is subject to the reuse conditions of [fedlex.admin.ch](https://www.fedlex.admin.ch/de/broadcasters) — free reuse for commercial and other purposes.
- **No guarantees:** This server is a community project, not affiliated with the Swiss Federal Chancellery. Availability depends on the upstream SPARQL endpoint.

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md)

---

## Security

See [SECURITY.md](SECURITY.md) for the security posture, hardening controls, and how to report a vulnerability.

---

## License

MIT License — see [LICENSE](LICENSE)

---

## Author

Hayal Oezkan . [malkreide](https://github.com/malkreide)

---

## Credits & Related Projects

- **Fedlex:** [fedlex.admin.ch](https://www.fedlex.admin.ch/) — Swiss Federal Chancellery
- **TERMDAT / LINDAS:** [lindas.admin.ch](https://lindas.admin.ch/) — Linked Data service of the Swiss administration
- **Protocol:** [Model Context Protocol](https://modelcontextprotocol.io/) — Anthropic / Linux Foundation
- **Related:** [parlament-mcp](https://github.com/malkreide) — Swiss Federal Assembly (parliamentary phase)
- **Related:** [swiss-democracy-mcp](https://github.com/malkreide) — Swiss federal popular votes (referendum phase)
- **Related:** [swiss-cultural-heritage-mcp](https://github.com/malkreide/swiss-cultural-heritage-mcp) — Swiss cultural heritage data
- **Related:** [zurich-opendata-mcp](https://github.com/malkreide/zurich-opendata-mcp) — City of Zurich open data
- **Related:** [swiss-transport-mcp](https://github.com/malkreide/swiss-transport-mcp) — Swiss public transport
- **Portfolio:** [Swiss Public Data MCP Portfolio](https://github.com/malkreide)

<!-- mcp-name: io.github.malkreide/fedlex-mcp -->

<!-- BEGIN GENERATED: install -->
## Installation

Run via [`uv`](https://docs.astral.sh/uv/)'s `uvx` — no clone or manual install needed. Add to your MCP client config (`mcpServers` for Claude Desktop, Cursor and Windsurf; use a top-level `servers` key for VS Code in `.vscode/mcp.json`):

```json
{
  "mcpServers": {
    "fedlex-mcp": {
      "command": "uvx",
      "args": [
        "fedlex-mcp"
      ]
    }
  }
}
```
<!-- END GENERATED: install -->
