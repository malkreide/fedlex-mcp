# Use Cases & Beispiele — fedlex-mcp

Hier finden Sie typische Anwendungsfälle für den `fedlex-mcp` Server, sortiert nach Zielgruppe.
Alle Beispiele können direkt in Claude (oder anderen MCP-Clients) in natürlicher Sprache abgefragt werden.
**Für diesen Server wird kein API-Key benötigt.**

---

### 🏫 Bildung & Schule
Lehrpersonen, Schulbehörden, Fachreferent:innen

**Gültige Bildungsgesetze finden**
«Zeig mir alle aktuell gültigen Bundesgesetze und Verordnungen zum Thema Berufsbildung.»
→ `fedlex_search_laws(keywords="Berufsbildung", in_force_only=True)`
*Warum nützlich:* Hilft Schulleitungen und Lehrkräften, rasch die aktuell geltenden rechtlichen Grundlagen im Bildungsbereich zu überblicken, ohne manuell in der Systematischen Rechtssammlung suchen zu müssen.

**Änderungen im Schulrecht antizipieren**
«Welche Erlasse im Bildungsbereich treten in den nächsten 180 Tagen in Kraft?»
→ `fedlex_get_upcoming_changes(days_ahead=180)`
*Warum nützlich:* Schulbehörden können sich proaktiv auf kommende gesetzliche Änderungen (z.B. neue Verordnungen) einstellen, bevor diese wirksam werden.

**Internationale Bildungsabkommen prüfen**
«Welche Staatsverträge hat die Schweiz zum Thema Bildung abgeschlossen?»
→ `fedlex_search_treaties(keywords="Bildung")`
*Warum nützlich:* Für Fachreferent:innen und Forschende, die die rechtlichen Rahmenbedingungen der internationalen Zusammenarbeit (z.B. Austauschprogramme) verstehen müssen.

---

### 👨‍👩‍👧 Eltern & Schulgemeinde
Elternräte, interessierte Erziehungsberechtigte

**Datenschutz an Schulen verstehen**
«Was genau steht im Datenschutzgesetz (DSG) und ist die Version von 1992 noch in Kraft?»
→ `fedlex_get_law_by_sr(sr_number="235.1")`
*Warum nützlich:* Erlaubt Elternräten, die rechtlichen Grundlagen zum Schutz der Daten ihrer Kinder schnell nachzuschlagen und sicherzustellen, dass sie sich auf die aktuellste Rechtslage stützen.

**Zukünftige Gesetze zur Familienpolitik**
«Hat der Bundesrat in letzter Zeit etwas zum Thema Familie oder Mutterschaftsurlaub im Bundesblatt publiziert?»
→ `fedlex_search_gazette(keywords="Familie")`
→ `fedlex_search_gazette(keywords="Mutterschaft")`
*Warum nützlich:* Hilft Eltern und Interessenvertretungen, frühzeitig von politischen Vorstössen und Botschaften zu erfahren, die Familien direkt betreffen.

---

### 🗳️ Bevölkerung & öffentliches Interesse
Allgemeine Öffentlichkeit, politisch und gesellschaftlich Interessierte

**Neueste Bundesbeschlüsse verfolgen**
«Was wurde in den letzten 14 Tagen in der Amtlichen Sammlung neu publiziert?»
→ `fedlex_get_recent_publications(days=14)`
*Warum nützlich:* Bietet politisch Interessierten einen transparenten und schnellen Überblick über alle neu erlassenen oder geänderten Gesetze auf Bundesebene.

**Historische Entwicklung von Gesetzen**
«Zeig mir die Versionsgeschichte der Bundesverfassung (SR 101).»
→ `fedlex_get_law_history(sr_number="101")`
*Warum nützlich:* Macht die historische Entwicklung wichtiger Gesetze nachvollziehbar und fördert das Verständnis für den stetigen Wandel des Schweizer Rechts.

---

### 🤖 KI-Interessierte & Entwickler:innen
MCP-Enthusiast:innen, Forscher:innen, Prompt Engineers, öffentliche Verwaltung

**Gesetzessuche automatisieren**
«Suche alle Erlasse zum Thema 'Künstliche Intelligenz' und zeige mir deren Metadaten.»
→ `fedlex_search_laws(keywords="Künstliche Intelligenz", in_force_only=False)`
*Warum nützlich:* Entwickler:innen können die Fedlex-Tools nutzen, um rechtliche Recherchen in eigene Agenten-Workflows zu integrieren.

**Portfolio-Synergie: Gesetzgebung und Parlamentsdebatten (Multi-Server)**
«Suche im Bundesblatt nach 'E-ID' und finde anschliessend mit dem swiss-democracy-mcp heraus, welche parlamentarischen Vorstösse es aktuell dazu gibt.»
→ `fedlex_search_gazette(keywords="E-ID")`
→ `curia_search_business(keywords="E-ID")` *(via [https://github.com/malkreide/swiss-democracy-mcp](https://github.com/malkreide/swiss-democracy-mcp))*
*Warum nützlich:* Zeigt die Mächtigkeit der Kombination von amtlichen Publikationen (Bundesblatt) mit den laufenden parlamentarischen Debatten für ein lückenloses politisches Monitoring.

**Portfolio-Synergie: Rechtsgrundlagen und offene Daten (Multi-Server)**
«Prüfe die gesetzlichen Grundlagen zur Preisbekanntgabe und frage dann das BFS nach aktuellen Inflationsdaten.»
→ `fedlex_search_laws(keywords="Preisbekanntgabe")`
→ `bfs_search_data(query="Inflation")` *(via [https://github.com/malkreide/swiss-statistics-mcp](https://github.com/malkreide/swiss-statistics-mcp))*
*Warum nützlich:* Verbindet rechtliche Rahmenbedingungen direkt mit den resultierenden statistischen Fakten für umfassende Analysen.

---

### 🔧 Technische Referenz: Tool-Auswahl nach Anwendungsfall

| Ich möchte… | Tool(s) | Auth nötig? |
|-------------|---------|-------------|
| **geltendes Recht nach Stichwort durchsuchen** | `fedlex_search_laws` | Nein |
| **die Details eines bestimmten Erlasses (z.B. DSG) sehen** | `fedlex_get_law_by_sr` | Nein |
| **wissen, welche Gesetze demnächst in Kraft treten** | `fedlex_get_upcoming_changes` | Nein |
| **die neuesten Publikationen (AS) des Bundes abrufen** | `fedlex_get_recent_publications` | Nein |
| **Botschaften und Vorstösse im Bundesblatt (BBl) suchen** | `fedlex_search_gazette` | Nein |
| **alle bisherigen Fassungen eines Gesetzes auflisten** | `fedlex_get_law_history` | Nein |
| **internationale Abkommen der Schweiz finden** | `fedlex_search_treaties` | Nein |
| **offene Vernehmlassungen und ihre Fristen überwachen** | `fedlex_get_open_consultations` | Nein |
| **Vernehmlassungen nach Thema/Status/Amt durchsuchen** | `fedlex_search_consultations` | Nein |
| **eine Vernehmlassung im Detail (inkl. Unterlagen) ansehen** | `fedlex_get_consultation` | Nein |
| **einen Fachbegriff in andere Landessprachen übersetzen** | `termdat_lookup_term` | Nein |
| **einen vollständigen TERMDAT-Eintrag abrufen** | `termdat_get_concept` | Nein |

---

### 🏛️ Vernehmlassungen & Terminologie (v1.1.0)

**Anchor-Demo: von der offenen Vernehmlassung zur mehrsprachigen Stellungnahme**
«Welche Vernehmlassungen mit Bildungsbezug laufen aktuell, bis wann läuft die Frist, welches Amt ist federführend — und wie lauten die zentralen Fachbegriffe auf Französisch und Italienisch für die Stellungnahme?»
→ `fedlex_get_open_consultations(topic="education")`
→ `fedlex_get_consultation(event_id="proj/2026/71/cons_1")`
→ `termdat_lookup_term(term="Volksschule", target_languages=["fr","it"])`
*Warum nützlich:* Fedlex sagt, worauf man antworten muss und bis wann (jede offene Vorlage mit `days_remaining` in Europe/Zurich); TERMDAT sagt, wie man es in den anderen Landessprachen nennt. `topic="education"` statt `keyword="Volksschule"` — der Ankerbegriff selbst kommt in null Titeln vor; die gesuchte Stichwort-Union wird in der Antwort ausgewiesen.

**Fristen-Monitoring**
«Auf welche Bundesvorlagen kann man gerade noch Stellung nehmen, sortiert nach Frist?»
→ `fedlex_get_open_consultations(limit=20)`
*Warum nützlich:* Filtert über die Frist (`eventEndDate >= heute`, Europe/Zurich, Kalendertag), sortiert nach kürzester Restfrist. Jeder Treffer führt `days_remaining` (0 = heute) und einen abgeleiteten `status` — eine abgelaufene Vorlage erscheint nie als laufend; Widersprüche zum Quell-Status werden mit `status_conflict: true` markiert.

**Portfolio-Synergie: Prozesskette Vernehmlassung → Parlament → Referendum**
«Zeig mir die laufende Vernehmlassung zum Thema X, dann die parlamentarische Behandlung und schliesslich eine allfällige Volksabstimmung.»
→ `fedlex_search_consultations(keyword="X")` *(dieser Server)*
→ `parlament-mcp` *(parlamentarische Phase, [github.com/malkreide](https://github.com/malkreide))*
→ `swiss-democracy-mcp` *(Referendumsphase, [github.com/malkreide](https://github.com/malkreide))*
*Warum nützlich:* Bildet den gesamten Gesetzgebungs-Lebenszyklus über drei aufeinander abgestimmte MCP-Server ab.

> ℹ️ **Hinweis zu TERMDAT:** Über LINDAS sind 77'692 von rund 400'000 Einträgen als Linked Data publiziert. Ein negativer Treffer bedeutet nicht, dass der Begriff in TERMDAT fehlt, sondern nur, dass er nicht im publizierten Teilbestand liegt.
