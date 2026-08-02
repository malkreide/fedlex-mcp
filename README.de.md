[:gb: English Version](README.md)

> :switzerland: **Teil des [Swiss Public Data MCP Portfolios](https://github.com/malkreide)**

# :balance_scale: fedlex-mcp

![Version](https://img.shields.io/badge/version-2.0.1-blue)
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
fedlex_get_open_consultations(topic="education")
   → fedlex_get_consultation(event_id="proj/2026/71/cons_1")
   → termdat_lookup_term(term="Volksschule", target_languages=["fr","it"])
```

Jede offene Vernehmlassung fuehrt `deadline`, `days_remaining` (zur Laufzeit in
Europe/Zurich berechnet, `0` = Frist heute) und einen **abgeleiteten** `status`
-- eine abgelaufene Vernehmlassung erscheint nie als laufend. Fedlex sagt,
*worauf* man antworten muss und *bis wann*; TERMDAT sagt, *wie es heisst* in den
anderen Landessprachen.

> **`topic="education"` statt `keyword="Volksschule"`.** Fedlex-Vernehmlassungen
> haben keine Sachgebiets-Taxonomie -- gefiltert wird per Freitext im Titel, und
> das Wort «Volksschule» kommt in **null** Vernehmlassungstiteln vor. Der
> `topic`-Filter expandiert zu einer ausgewiesenen Stichwort-Union (Bildung,
> Schule, Berufsbildung, Hochschule, …) und nennt in der Antwort die gesuchten
> Begriffe.

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
| 8 | `fedlex_get_open_consultations` | Fedlex | **Fristen-Monitoring** -- offene Vernehmlassungen (`eventEndDate >= heute`, Europe/Zurich); je mit `days_remaining` + abgeleitetem `status`, sortiert nach kuerzester Restfrist; optional `topic`/`keyword` |
| 9 | `fedlex_search_consultations` | Fedlex | Volltextsuche ueber Titel/Beschreibung, mit Filtern (topic, status, Fristzeitraum, Amt) |
| 10 | `fedlex_get_consultation` | Fedlex | Detail zu einer `eventId`: Frist, `days_remaining`, Amt, abgeleiteter Status, Unterlagen |
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
  +-- jolux:eventDescription            mehrsprachig
  +-- jolux:consultationStatus          -> Vokabular-URI (0..6, /2 = «Laufend»)
  +-- jolux:foreseenImpactToLegalResource  -> die betroffene Rechtsressource (Link zur SR)
  +-- jolux:hasSubTask  ->  ?t
        +-- jolux:eventStartDate                      <- opened_on
        +-- jolux:eventEndDate                        <- die Frist (xsd:date, Kalendertag)
        +-- jolux:institutionInChargeOfTheEvent       <- federfuehrendes Departement
        +-- jolux:institutionInChargeOfTheEventLevel2 <- federfuehrendes Amt
        +-- jolux:opinionHasDraftRelatedDocument      <- Vernehmlassungsunterlagen
```

Es gibt **keine** Sachgebiets-Taxonomie auf `jolux:Consultation` -- thematische
Filterung erfolgt per Freitext nur ueber `eventTitle`; `status` wird aus der
Frist abgeleitet, nicht aus dem Quell-Statusfeld.

**Gesetzgebungs-Lebenszyklus -- wo Vernehmlassungen stehen (alles in diesem Server):**

```
  Vernehmlassung            Bundesblatt (BBl)          Systematische Sammlung (SR)
  (vorparlamentarisch) ───► (Botschaft / Erlasstext)─► (konsolidiertes Recht in Kraft)
  ────────────────         ─────────────────────      ───────────────────────────
  fedlex_get_open_          fedlex_search_gazette      fedlex_search_laws
    consultations           (eli/fga/…)                fedlex_get_law_by_sr
  fedlex_search_                                       fedlex_get_law_history
    consultations                                      (eli/cc/…)
  fedlex_get_consultation
        │  jolux:foreseenImpactToLegalResource
        └───────────────────────────────────────────► verknuepft eine Vernehmlassung
                                                       mit der SR-Ressource, die sie aendert
```

Die Vernehmlassung ist der **frueheste** oeffentliche Einflusspunkt -- die Tools
oben sagen *was offen ist und bis wann*, bevor eine Vorlage das Bundesblatt erreicht.

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

### Vernehmlassungen -- Geltungsbereich und Zuverlaessigkeit (zuerst lesen)

- **Nur Bund. Keine kantonalen Vernehmlassungen.** Fedlex fuehrt *Bundes*-
  Vernehmlassungen. Kantonale Vernehmlassungen -- fuer ein Schulamt oft die
  relevanteren -- sind **nicht** in Fedlex und **nicht** abgedeckt. Das ist eine
  harte Bereichsgrenze, kein umgehbarer Mangel.
- **Kein Push-Dienst.** MCP ist Pull-basiert: Der Server sagt *auf Abruf*, was
  laeuft und was bald auslaeuft. Er kann nicht benachrichtigen, terminieren oder
  alarmieren. Die Wiederholung kommt von dir oder einem externen Scheduler --
  nie vom Server. «Keine offenen Vernehmlassungen» heisst *jetzt nichts offen*,
  nicht *nichts kommt*.
- **Thematische Filterung ist Freitext -- und unscharf.** `jolux:Consultation`
  hat **keine** Sachgebiets-Taxonomie (live verifiziert 2026-07-20) -- gefiltert
  wird per Teilstring im Titel. `topic="education"` expandiert zu einer
  ausgewiesenen Stichwort-Union und ueber-matcht bewusst (ein zu enger Filter
  wuerde faelschlich beruhigen); es sind Falsch-Positive moeglich (z.B.
  «Ausbildung» in einem unverwandten Titel) und, bei Nischenwortlaut, auch
  Falsch-Negative. Die Antwort nennt stets die gesuchten Begriffe.
- **Abdeckung / Latenz:** ~2 553 Vernehmlassungen; der historische Bestand
  1960-1991 liegt beim Bundesarchiv, **ausserhalb dieses Scopes**. Neu
  eroeffnete Vernehmlassungen erscheinen mit der Publikationslatenz von Fedlex
  (nicht in Echtzeit).
- **Fristen enden am Kalendertag** in Europe/Zurich; `days_remaining` wird zur
  Laufzeit berechnet, nie gecacht. `0` = Frist endet heute.

**Live-Befunde (verifiziert 2026-07-20):**

| Abfrage | Status | Records | Bemerkung |
|---|---|---|---|
| `COUNT(?s) {?s a jolux:Consultation}` | OK | **2 553** | Gesamtbestand |
| `hasSubTask` mit Start-/Enddatum | OK | 2 505 von 2 553 | **48 ohne Fristen** |
| Offene Vernehmlassungen (`eventEndDate >= heute`) | OK | **42** | Fristen bis Herbst 2026 |
| Status-Vokabular `consultation-status` | OK | 7 Werte | `/0`..`/6`, `/2` = «Laufend» |
| Titel enthaelt «volksschule» / «lehrplan» | OK | **0 / 0** | Ankerbegriff selbst findet nichts → `topic` nutzen |
| Titel enthaelt «bildung» (einzeln) vs. `topic="education"` | OK | 44 vs. 66 | Stichwort-Union ist breiter |
| `REGEX(LCASE(?t), "a\|b")`-Alternation | **KAPUTT** | 0 | auf diesem Endpoint still leer → OR-verkettetes `CONTAINS` |

- **Quirk 1 -- die Frist gewinnt ueber das Statusfeld.** Status `/2` («Laufend»)
  und `eventEndDate` sind **zwei unabhaengige Signale**. Der Server leitet
  `status` aus dem **Datum** ab: Frist vorbei ⇒ `Abgeschlossen`, egal was das
  Quellfeld sagt -- eine abgelaufene Vernehmlassung wird nie als laufend
  gelistet. Widersprechen sich die Signale, wird der Datensatz mit
  `status_conflict: true` markiert und behaelt das rohe Label in `status_source`.

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

## Was dieses Tool **nicht** ist

- **Kein Abo, kein Alerting.** Es beobachtet nicht, benachrichtigt nicht,
  erinnert nicht. Es antwortet auf Abruf. Jede wiederkehrende Pruefung steuerst
  du oder ein externer Scheduler -- ausserhalb des Servers.
- **Keine kantonale Quelle.** Nur Bundes-Vernehmlassungen -- siehe Bekannte
  Einschraenkungen.
- **Keine Rechtsberatung.** Geliefert werden oeffentliche Metadaten und Links zu
  amtlichen Dokumenten. Frist und Status werden mechanisch aus den publizierten
  Daten abgeleitet; entscheidungskritisches bitte gegen die verlinkte
  Fedlex-Seite pruefen.

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

## Mitwirken

Siehe [CONTRIBUTING.md](CONTRIBUTING.md) (bzw. [CONTRIBUTING.de.md](CONTRIBUTING.de.md))

---

## Sicherheit

Siehe [SECURITY.md](SECURITY.md) (bzw. [SECURITY.de.md](SECURITY.de.md)) für die Sicherheitslage, Härtungsmassnahmen und das Melden von Schwachstellen.

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
