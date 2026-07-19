[:gb: English Version](README.md)

> :switzerland: **Teil des [Swiss Public Data MCP Portfolios](https://github.com/malkreide)**

# :balance_scale: fedlex-mcp

![Version](https://img.shields.io/badge/version-1.1.0-blue)
[![Lizenz: MIT](https://img.shields.io/badge/Lizenz-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-purple)](https://modelcontextprotocol.io/)
[![Kein API-Schluessel](https://img.shields.io/badge/Auth-keiner%20erforderlich-brightgreen)](https://github.com/malkreide/fedlex-mcp)
![CI](https://github.com/malkreide/fedlex-mcp/actions/workflows/ci.yml/badge.svg)

> MCP-Server fuer Schweizer Bundesrecht, Vernehmlassungen und amtliche Terminologie -- SR durchsuchen, Vernehmlassungsfristen ueberwachen und Begriffe zwischen den Landessprachen uebersetzen via Claude Desktop oder Claude.ai

---

## Uebersicht

`fedlex-mcp` verbindet KI-Assistenten (Claude) mit drei amtlichen Schweizer SPARQL-Datenquellen:

1. **Bundesrecht** ueber den **Fedlex SPARQL-Endpoint** -- Systematische Rechtssammlung (SR), Amtliche Sammlung (AS), Bundesblatt (BBl) und Staatsvertraege.
2. **Vernehmlassungen** ueber denselben Fedlex-Endpoint (`jolux:Consultation`) -- das vorparlamentarische Verfahren, in dem zu einer Vorlage Stellung genommen werden kann.
3. **TERMDAT**, die Terminologiedatenbank der Bundeskanzlei, ueber den **LINDAS SPARQL-Endpoint** -- amtliche Begriffs-Entsprechungen in de/fr/it/rm/en.

Alle drei sind SPARQL-basiert -- genau deshalb liegen sie in einem Server statt in dreien: kein neuer Technologie-Stack, nur neue Queries gegen bekannte Muster.

**Metapher:** USB-C fuer Bundesrecht. *Fedlex sagt, worauf man antworten muss. TERMDAT sagt, wie man es in den anderen Landessprachen nennt.*

---

## Funktionen

- :balance_scale: **12 Tools, 2 Resources** fuer Bundesrecht, Vernehmlassungen und Terminologie
- :mag: **SPARQL-basiert** -- zwei isolierte Endpoints (Fedlex + LINDAS), kein gemeinsamer Ausfallpunkt
- :globe_with_meridians: **5 Sprachen** -- Deutsch, Franzoesisch, Italienisch, Raetoromanisch, plus Englisch fuer Terminologie
- :unlock: **Kein API-Schluessel erforderlich** -- alle Daten unter offener Wiederverwendungslizenz
- :cloud: **Dualer Transport** -- stdio (Claude Desktop) + Streamable HTTP (Cloud)

---

## Anchor-Demo-Abfrage

> *«Welche Vernehmlassungen mit Bildungsbezug laufen aktuell, bis wann laeuft die Frist, welches Amt ist federfuehrend -- und wie lauten die zentralen Fachbegriffe auf Franzoesisch und Italienisch fuer die Stellungnahme?»*

Ein einziges Gespraech verkettet drei Tools ueber zwei Endpoints:

```
fedlex_get_open_consultations(keyword="Bildung")
   → fedlex_get_consultation(event_id="proj/2026/71/cons_1")
   → termdat_lookup_term(term="Volksschule", target_languages=["fr","it"])
```

Fedlex sagt, *worauf* man antworten muss und *bis wann*; TERMDAT sagt, *wie es heisst* in den anderen Landessprachen.

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

> *«Zeig mir alle gueltigen Bundesgesetze zur Berufsbildung»*
> *«Was steht im Datenschutzgesetz? Ist es noch in Kraft?»*
> *«Welche Vernehmlassungen zur Bildung laufen aktuell, und bis wann?»*
> *«Wie heisst ‹Volksschule› auf Franzoesisch und Italienisch in der amtlichen Terminologie?»*

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

| # | Tool | Quelle | Beschreibung |
|---|------|--------|-------------|
| 1 | `fedlex_search_laws` | Fedlex | Erlasse der SR nach Stichwort im Titel suchen |
| 2 | `fedlex_get_law_by_sr` | Fedlex | Erlass nach SR-Nummer abrufen (z.B. `235.1` = DSG) |
| 3 | `fedlex_get_recent_publications` | Fedlex | Neueste Publikationen der Amtlichen Sammlung (AS) |
| 4 | `fedlex_get_upcoming_changes` | Fedlex | Erlasse, die bald in Kraft treten (Rechtsmonitoring) |
| 5 | `fedlex_search_gazette` | Fedlex | Im Bundesblatt (BBl) suchen |
| 6 | `fedlex_get_law_history` | Fedlex | Alle Fassungen eines Erlasses (Versionsgeschichte) |
| 7 | `fedlex_search_treaties` | Fedlex | Staatsvertraege (SR-Nummern beginnen mit `0.`) |
| 8 | `fedlex_get_open_consultations` | Fedlex | **Fristen-Monitoring** -- offene Vernehmlassungen, gefiltert ueber `eventEndDate >= heute` |
| 9 | `fedlex_search_consultations` | Fedlex | Volltextsuche ueber Titel/Beschreibung von Vernehmlassungen, mit Filtern |
| 10 | `fedlex_get_consultation` | Fedlex | Detail zu einer `eventId`: Fristen, Amt, Status, Unterlagen |
| 11 | `termdat_lookup_term` | LINDAS | Begriff → Entsprechungen in de/fr/it/rm/en inkl. Definition |
| 12 | `termdat_get_concept` | LINDAS | Vollstaendiger TERMDAT-Eintrag zu einer URI oder ID |

### Beispiel-Abfragen

| Abfrage | Tool |
|---------|------|
| *«Zeig mir alle gueltigen Bundesgesetze zur Berufsbildung»* | `fedlex_search_laws` |
| *«Was steht im Datenschutzgesetz?»* | `fedlex_get_law_by_sr` |
| *«Welche Gesetze treten in den naechsten 3 Monaten in Kraft?»* | `fedlex_get_upcoming_changes` |
| *«Zeig mir die Versionsgeschichte des DSG»* | `fedlex_get_law_history` |
| *«Welche Vernehmlassungen zur Bildung sind offen, und bis wann?»* | `fedlex_get_open_consultations` |
| *«Finde abgeschlossene Vernehmlassungen zum Sprachengesetz»* | `fedlex_search_consultations` |
| *«Gib mir Detail und Unterlagen zur Vernehmlassung proj/2026/71/cons_1»* | `fedlex_get_consultation` |
| *«Wie heisst ‹Volksschule› auf Franzoesisch und Italienisch?»* | `termdat_lookup_term` |
| *«Zeig den vollstaendigen TERMDAT-Eintrag 40109»* | `termdat_get_concept` |

→ Weitere Anwendungsbeispiele nach Zielgruppe →

---

## Architektur

Zwei isolierte SPARQL-Endpoints hinter einem Server. Getrennte httpx-Clients und
Timeouts sorgen dafuer, dass ein LINDAS-Ausfall die `fedlex_*`-Tools nie
beeintraechtigt -- und umgekehrt.

```
+-------------------+     +------------------------------+     +--------------------------+
|   Claude / KI     |---->|  Fedlex MCP                  |---->|  Fedlex SPARQL Endpoint  |
|   (MCP Host)      |<----|  (MCP Server)                |<----|  fedlex.data.admin.ch    |
+-------------------+     |                              |     |  (Recht + Vernehmlass.)  |
                          |  12 Tools . 2 Resources      |     +--------------------------+
                          |  Stdio | SSE                 |
                          |                              |     +--------------------------+
                          |  Isolierte Clients:          |---->|  LINDAS SPARQL Endpoint  |
                          |   - Fedlex  (Recht + Vernl.)  |<----|  lindas.admin.ch/query   |
                          |   - LINDAS  (TERMDAT)         |     |  (fch/termdat, TERMDAT)  |
                          |                              |     +--------------------------+
                          |  Keine Authentifizierung     |
                          +------------------------------+
```

### Datenmodell

**JOLux-Ontologie -- Bundesrecht (Fedlex)**

```
jolux:ConsolidationAbstract  <-  SR-Eintrag
  +-- jolux:isRealizedBy  ->  jolux:Expression (URI endet auf /de, /fr, /it, /rm)
     +-- jolux:title               "Bundesgesetz vom 19. Juni 1992 ueber den Datenschutz"
     +-- jolux:titleShort          "DSG"
     +-- jolux:historicalLegalId   "235.1"

jolux:inForceStatus:  .../0 In Kraft  ·  .../1 Nicht mehr in SR publiziert  ·  .../3 Nicht mehr in Kraft
```

**JOLux-Ontologie -- Vernehmlassungen (Fedlex, gleicher Endpoint)**

```
jolux:Consultation
  +-- jolux:eventId               "proj/2026/71/cons_1"
  +-- jolux:eventTitle            mehrsprachig (de/fr/it)
  +-- jolux:eventDescription      mehrsprachig
  +-- jolux:consultationStatus    -> Vokabular-URI (0..6, /2 = «Laufend»)
  +-- jolux:hasSubTask  ->  ?t
        +-- jolux:eventStartDate
        +-- jolux:eventEndDate                        <- die Frist
        +-- jolux:institutionInChargeOfTheEvent       <- federfuehrendes Departement
        +-- jolux:institutionInChargeOfTheEventLevel2 <- federfuehrendes Amt
        +-- jolux:opinionHasDraftRelatedDocument      <- Vernehmlassungsunterlagen
```

**schema.org -- Terminologie (TERMDAT via LINDAS, Graph `fch/termdat`)**

```
<Konzept>  = https://register.ld.admin.ch/termdat/40109      (a schema.ld.admin.ch/Term, ValidatedEntry)
  +-- schema:name         bevorzugte Benennung je Sprache (de/fr/it/en; rm faktisch leer)
  +-- schema:description  mehrsprachige Definition
  +-- schema:hasPart  ->  <Term> = .../termdat/40109/3/de     (Synonym/Variante, Sprach- + Positionssuffix)
```

**SPARQL-Endpoints:** `https://fedlex.data.admin.ch/sparqlendpoint` · `https://lindas.admin.ch/query`
**Lizenz:** Freie Wiederverwendung gemaess [fedlex.admin.ch](https://www.fedlex.admin.ch/de/broadcasters); TERMDAT via LINDAS unter offener Wiederverwendung.

---

## Architektur-Entscheid

**ARCH A -- Live-SPARQL-only**, fuer alle drei Datenbereiche, konsistent zur
bestehenden Fedlex-Anbindung (entschieden am 18.07.2026).

Beide Quellen sind SPARQL-Endpoints ohne Auth mit akzeptabler Latenz, deshalb ist
kein Dump-/Offline-Fallback noetig: Faellt der Fedlex-Endpoint aus, ist der Server
ohnehin nicht funktionsfaehig, und ein Cache wuerde das nur verschleiern. LINDAS
ist ein **separater** Endpoint; dessen Ausfall darf die `fedlex_*`-Tools
**nicht** beeintraechtigen.

**Isolationspflicht:** Fedlex und LINDAS nutzen getrennte httpx-Clients, getrennte
Timeouts und getrennte Fehler-/Statusmeldung. Ein LINDAS-Timeout kann keinen
`fedlex_*`-Aufruf zum Scheitern bringen und umgekehrt (durch einen
Isolations-Test abgedeckt).

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
|   +-- server.py                # 12 Tools, 2 Resources (Fedlex + LINDAS)
+-- tests/
|   +-- test_server.py           # Unit-Tests (gemockt)
+-- .github/workflows/ci.yml     # GitHub Actions (Python 3.11/3.12/3.13)
+-- pyproject.toml
+-- CHANGELOG.md
+-- CONTRIBUTING.md               # Mitwirken-Leitfaden (Englisch)
+-- CONTRIBUTING.de.md            # Mitwirken-Leitfaden (Deutsch)
+-- SECURITY.md                   # Sicherheitsrichtlinie (Englisch)
+-- SECURITY.de.md                # Sicherheitsrichtlinie (Deutsch)
+-- LICENSE
+-- README.md                    # Englische Hauptversion
+-- README.de.md                 # Diese Datei (Deutsch)
```

---

## Bekannte Einschraenkungen

- **SPARQL-Komplexitaet:** Sehr breite Stichwortsuchen koennen ein Timeout verursachen (45s)
- **Sprachabdeckung:** Deutsch hat die vollstaendigsten Daten; andere Sprachen koennen Luecken aufweisen
- **Historische Daten:** Nicht alle historischen Fassungen haben maschinenlesbare Metadaten
- **Rate Limiting:** Die Endpoints koennen bei Hochfrequenz-Abfragen drosseln

### Vernehmlassungen (Fedlex) -- Befunde (verifiziert am 18.07.2026)

| Abfrage | Status | Records | Bemerkung |
|---|---|---|---|
| `COUNT(?s) {?s a jolux:Consultation}` | OK | **2 553** | Gesamtbestand |
| `hasSubTask` mit Start-/Enddatum | OK | 2 505 von 2 553 | **48 ohne Fristen** |
| Offene Vernehmlassungen (`eventEndDate >= heute`) | OK | 8+ | Fristen bis Sept. 2026 verifiziert |
| Status-Vokabular `consultation-status` | OK | 7 Werte | `/0`..`/6`, `/2` = «Laufend» |
| `previousConsultationStatus` | OK | nur 234 | duenn besetzt -- nicht als Filter genutzt |

- **Quirk 1 -- der Status allein reicht nicht.** Status `/2` («Laufend») und ein
  `eventEndDate` in der Zukunft sind **zwei unabhaengige Signale**, die
  auseinanderlaufen koennen: Es gibt «laufende» Eintraege mit bereits abgelaufener
  Frist, und 48 ohne jede Frist. `fedlex_get_open_consultations` filtert daher
  **primaer ueber `eventEndDate >= heute`**, nicht ueber den Status. Widersprechen
  sich die Signale, wird die Response explizit mit `status_conflict: true` markiert
  statt stillschweigend aufgeloest.

### TERMDAT (LINDAS) -- Befunde (verifiziert am 18.07.2026)

| Abfrage | Status | Records | Bemerkung |
|---|---|---|---|
| `COUNT(DISTINCT ?s) a schema.ld:Term` im Graph | OK | **77 692** | |
| Sprach-Tags auf `schema:name` | OK | de/fr/it/en | `rm` faktisch nicht besetzt (0) |
| Suche `schema:name = "Volksschule"` | OK | 1 | liefert Term-URI `…/termdat/40109/3/de` |
| Konzept-URI `…/termdat/40109` | OK | – | 4 Sprachvarianten + Definition |

- **Quirk 2 -- Reality-Check-Diskrepanz (ungeschoent).** Die Bundeskanzlei
  kommuniziert fuer TERMDAT rund **400 000** Eintraege. LINDAS enthaelt
  **77 692**. Die Differenz ist nicht erklaert -- vermutlich ist nur der
  validierte und freigegebene Teilbestand als Linked Data publiziert. **Ein
  negativer Terminologie-Treffer bedeutet nicht, dass der Begriff in TERMDAT
  fehlt, sondern nur, dass er nicht im LINDAS-Teilbestand liegt.** Dieser Hinweis
  steht in jeder TERMDAT-Response.
- **Quirk 3 -- zwei URI-Ebenen.** Konzept-URIs (`…/termdat/40109`) tragen die
  bevorzugten Benennungen und die Definition; Term-URIs mit Sprach-/Positionssuffix
  (`…/termdat/40109/3/de`) sind Synonyme/Varianten, verknuepft ueber
  `schema:hasPart`. Die Tools akzeptieren beide Formen und normalisieren intern auf
  die Konzept-ID.

---

## Verwandte Prozesse im Portfolio

Die Schweizer Bundesgesetzgebung ist eine Kette; dieser Server deckt einen Teil
davon ab -- die vorparlamentarische Vernehmlassung. Die vollstaendige Kette ist
ueber drei MCP-Server abbildbar:

```
Vernehmlassung  →  Botschaft  →  Parlament  →  Referendum
   fedlex-mcp      fedlex-mcp    parlament-mcp   swiss-democracy-mcp
```

- **Vernehmlassung (vorparlamentarisch):** dieser Server -- die `fedlex_*consultation*`-Tools.
- **Parlamentarische Phase:** [`parlament-mcp`](https://github.com/malkreide) -- Debatten, Vorstoesse, Abstimmungen der Bundesversammlung.
- **Volksabstimmung / Referendum:** [`swiss-democracy-mcp`](https://github.com/malkreide) -- eidgenoessische Volksabstimmungen. Vernehmlassungen sind eine eigene, fruehere Stufe -- keine Ueberschneidung, aber derselbe Gesetzgebungs-Lebenszyklus.

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

- **Read-only:** Alle 12 Tools fuehren ausschliesslich SPARQL SELECT-Abfragen durch -- kein Schreiben, Aendern oder Loeschen an einem der Endpoints. Alle Tools sind `readOnlyHint: true` / `destructiveHint: false` / `idempotentHint: true` annotiert.
- **Keine Personendaten:** Fedlex enthaelt oeffentliches Recht, Bekanntmachungen und Vernehmlassungs-Metadaten; TERMDAT amtliche Terminologie. Keine personenbezogenen Daten (PII) werden durch diesen Server verarbeitet oder gespeichert.
- **Rate Limits:** Die Fedlex- und LINDAS-SPARQL-Endpoints sind oeffentliche Dienste ohne dokumentiertes Rate Limit; verwende den `limit`-Parameter zurueckhaltend (Standard 20, Maximum 100). Der Server erzwingt ein 45s-Timeout pro Anfrage und Endpoint und wiederholt nur transiente Fehler.
- **Endpoint-Isolation:** Fedlex und LINDAS nutzen getrennte Clients und Timeouts -- ein LINDAS-Ausfall beeintraechtigt die `fedlex_*`-Tools nicht.
- **Datenaktualitaet:** Die Ergebnisse spiegeln die Endpoints zum Abfragezeitpunkt wider. Kein Caching wird durch diesen Server durchgefuehrt.
- **Nutzungsbedingungen:** Die Daten unterliegen den Wiederverwendungsbedingungen von [fedlex.admin.ch](https://www.fedlex.admin.ch/de/broadcasters) -- freie Wiederverwendung fuer kommerzielle und andere Zwecke.
- **Keine Gewaehr:** Dieser Server ist ein Community-Projekt, nicht verbunden mit der Schweizerischen Bundeskanzlei. Die Verfuegbarkeit haengt vom vorgelagerten SPARQL-Endpoint ab.

---

## Changelog

Siehe [CHANGELOG.md](CHANGELOG.md)

---

## Sicherheit

Siehe [SECURITY.md](SECURITY.md) (bzw. [SECURITY.de.md](SECURITY.de.md)) für die Sicherheitslage, Härtungsmassnahmen und das Melden von Schwachstellen.

---

## Mitwirken

Siehe [CONTRIBUTING.md](CONTRIBUTING.md) (bzw. [CONTRIBUTING.de.md](CONTRIBUTING.de.md))

---

## Lizenz

MIT-Lizenz -- siehe [LICENSE](LICENSE)

---

## Autor

Hayal Oezkan . [malkreide](https://github.com/malkreide)

---

## Credits & Verwandte Projekte

- **Fedlex:** [fedlex.admin.ch](https://www.fedlex.admin.ch/) -- Schweizerische Bundeskanzlei
- **TERMDAT / LINDAS:** [lindas.admin.ch](https://lindas.admin.ch/) -- Linked-Data-Dienst der Schweizer Verwaltung
- **Protokoll:** [Model Context Protocol](https://modelcontextprotocol.io/) -- Anthropic / Linux Foundation
- **Verwandt:** [parlament-mcp](https://github.com/malkreide) -- Bundesversammlung (parlamentarische Phase)
- **Verwandt:** [swiss-democracy-mcp](https://github.com/malkreide) -- eidgenoessische Volksabstimmungen (Referendumsphase)
- **Verwandt:** [swiss-cultural-heritage-mcp](https://github.com/malkreide/swiss-cultural-heritage-mcp) -- Schweizer Kulturerbe
- **Verwandt:** [zurich-opendata-mcp](https://github.com/malkreide/zurich-opendata-mcp) -- Open Data der Stadt Zuerich
- **Verwandt:** [swiss-transport-mcp](https://github.com/malkreide/swiss-transport-mcp) -- Oeffentlicher Verkehr CH
- **Portfolio:** [Swiss Public Data MCP Portfolio](https://github.com/malkreide)
