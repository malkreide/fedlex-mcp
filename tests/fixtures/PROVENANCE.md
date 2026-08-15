# Herkunft der Fixtures

**Erzeugt von `scripts/record_fixtures.py`. Nicht von Hand pflegen.**

Aufgezeichnet am **2026-08-15** von den beiden Endpunkten dieses
Servers: `https://fedlex.data.admin.ch/sparqlendpoint` und `https://lindas.admin.ch/query`.

Ohne Datum ist «aufgezeichnet» nach zwei Jahren von «ausgedacht» nicht
mehr zu unterscheiden — die Datei sieht gleich aus.

**Zwei Endpunkte, ein Dutzend Abfrageformen.** Die Form der Antwort
haengt hier an der Abfrage und nicht am Endpunkt: `get_law_history`
liefert andere Variablen als `search_treaties`. Die Portfolio-Regel
«eine Antwort je externem Endpunkt» waere mit zwei Dateien erfuellt und
truege fast nichts; aufgezeichnet ist deshalb eine Antwort je Abfrage,
die ein Werkzeug abschickt — auch dann, wenn ein Werkzeug mehrere
abschickt (dann durchnummeriert).

**Aufgezeichnet an der Naht, an der der Server die Antwort erhaelt.**
Der Recorder faehrt die Werkzeuge selbst und schneidet die
SPARQL-Schicht mit. Die Fixture ist damit per Konstruktion die Antwort
auf die Abfrage, die der Server wirklich stellt — eine von Hand
nachgebaute Abfrage waere schon wieder eine Annahme.

**Aufgezeichnet ist die rohe SPARQL-JSON-Antwort**, nicht die geparsten
Bindings. Der Parser gehoert zu dem, was geprueft werden soll.

`get_law_by_sr` und `get_law_history` fragen **dasselbe** Gesetz ab
(SR 235.1), damit die beiden Aufzeichnungen einen Gegenstand
beschreiben und nicht zwei.

Fehlerpfade — Timeouts, 5xx, eine kaputte Abfrage — bleiben
handgeschrieben. Die lassen sich nicht auf Zuruf aufzeichnen.

## `search_laws.json`

- **Werkzeug:** `fedlex_search_laws` (Abfrage 1 von 1)
- **Endpunkt:** `https://fedlex.data.admin.ch/sparqlendpoint`
- **Eingabe:** `{'keywords': 'Datenschutz', 'language': <Language.DE: 'de'>, 'in_force_only': True, 'limit': 3}`
- **Aufgezeichnet:** 2026-08-15
- **Groesse:** 1786 B (3 Ergebniszeilen, 3 Treffer im Werkzeug)
- **SHA-256:** `f06e53d6fb4edd1da4147e6c182f3c33a23b444e68fd958241e0050aaac6c899`

## `law_by_sr_1.json`

- **Werkzeug:** `fedlex_get_law_by_sr` (Abfrage 1 von 2)
- **Endpunkt:** `https://fedlex.data.admin.ch/sparqlendpoint`
- **Eingabe:** `{'sr_number': '235.1', 'language': <Language.DE: 'de'>}`
- **Aufgezeichnet:** 2026-08-15
- **Groesse:** 722 B (1 Ergebniszeilen, 1 Treffer im Werkzeug)
- **SHA-256:** `295ed0f1e83a116d194f38be9423ff9c3776b41b9fddc72d6ce3f24950d072d1`

## `law_by_sr_2.json`

- **Werkzeug:** `fedlex_get_law_by_sr` (Abfrage 2 von 2)
- **Endpunkt:** `https://fedlex.data.admin.ch/sparqlendpoint`
- **Eingabe:** `{'sr_number': '235.1', 'language': <Language.DE: 'de'>}`
- **Aufgezeichnet:** 2026-08-15
- **Groesse:** 571 B (1 Ergebniszeilen, 1 Treffer im Werkzeug)
- **SHA-256:** `e6374572bca27ad43a0366157f794f053cf96c70b141c913bc4458aabbe26321`

## `recent_publications.json`

- **Werkzeug:** `fedlex_get_recent_publications` (Abfrage 1 von 1)
- **Endpunkt:** `https://fedlex.data.admin.ch/sparqlendpoint`
- **Eingabe:** `{'days': 30, 'language': <Language.DE: 'de'>, 'limit': 3}`
- **Aufgezeichnet:** 2026-08-15
- **Groesse:** 1167 B (3 Ergebniszeilen, 3 Treffer im Werkzeug)
- **SHA-256:** `a46675d2b60eebeb57b07c668ad4ddd9afee0a2a8abfe71c20d9d10f4424c81d`

## `upcoming_changes.json`

- **Werkzeug:** `fedlex_get_upcoming_changes` (Abfrage 1 von 1)
- **Endpunkt:** `https://fedlex.data.admin.ch/sparqlendpoint`
- **Eingabe:** `{'days_ahead': 90, 'language': <Language.DE: 'de'>, 'limit': 20}`
- **Aufgezeichnet:** 2026-08-15
- **Groesse:** 1768 B (4 Ergebniszeilen, 4 Treffer im Werkzeug)
- **SHA-256:** `cfdbeb02f03c9bc099f2e649265d1d0901e251ae6013405e87f721b45175ed51`

## `gazette.json`

- **Werkzeug:** `fedlex_search_gazette` (Abfrage 1 von 1)
- **Endpunkt:** `https://fedlex.data.admin.ch/sparqlendpoint`
- **Eingabe:** `{'keywords': 'Bildung', 'language': <Language.DE: 'de'>, 'year': None, 'limit': 3}`
- **Aufgezeichnet:** 2026-08-15
- **Groesse:** 1060 B (3 Ergebniszeilen, 3 Treffer im Werkzeug)
- **SHA-256:** `a7d0703a151f52fff8ed4c018977601981319d52b4ffd0f0f6a55b515c2866c9`

## `law_history.json`

- **Werkzeug:** `fedlex_get_law_history` (Abfrage 1 von 1)
- **Endpunkt:** `https://fedlex.data.admin.ch/sparqlendpoint`
- **Eingabe:** `{'sr_number': '235.1', 'language': <Language.DE: 'de'>}`
- **Aufgezeichnet:** 2026-08-15
- **Groesse:** 654 B (1 Ergebniszeilen, 1 Treffer im Werkzeug)
- **SHA-256:** `966c23c7f0c6d22afb4f8648cc042a64f2d05d4aae5875e79e7a488dd2ade082`

## `treaties.json`

- **Werkzeug:** `fedlex_search_treaties` (Abfrage 1 von 1)
- **Endpunkt:** `https://fedlex.data.admin.ch/sparqlendpoint`
- **Eingabe:** `{'keywords': 'Bildung', 'language': <Language.DE: 'de'>, 'limit': 3}`
- **Aufgezeichnet:** 2026-08-15
- **Groesse:** 1903 B (3 Ergebniszeilen, 3 Treffer im Werkzeug)
- **SHA-256:** `dc813bb684bb871d907eeca6b04f5cca891dae95d3dddeace8fe9a5187683f91`

## `open_consultations.json`

- **Werkzeug:** `fedlex_get_open_consultations` (Abfrage 1 von 1)
- **Endpunkt:** `https://fedlex.data.admin.ch/sparqlendpoint`
- **Eingabe:** `{'keyword': None, 'topic': None, 'language': <Language.DE: 'de'>, 'limit': 20}`
- **Aufgezeichnet:** 2026-08-15
- **Groesse:** 17255 B (20 Ergebniszeilen, 20 Treffer im Werkzeug)
- **SHA-256:** `88ae1c5903952156f171a6cafc19c6322a1b39a0c0ed5215996fcd1e52dba907`

## `termdat_lookup_1.json`

- **Werkzeug:** `termdat_lookup_term` (Abfrage 1 von 2)
- **Endpunkt:** `https://lindas.admin.ch/query`
- **Eingabe:** `{'term': 'Volksschule', 'target_languages': [<TermLanguage.DE: 'de'>, <TermLanguage.FR: 'fr'>, <TermLanguage.IT: 'it'>, <TermLanguage.RM: 'rm'>, <TermLanguage.EN: 'en'>], 'limit': 20}`
- **Aufgezeichnet:** 2026-08-15
- **Groesse:** 372 B (1 Ergebniszeilen, 1 Treffer im Werkzeug)
- **SHA-256:** `b0d436ae110f536a535204632ced6ca2647e9ea844a04e4dc62aca113f59cdd3`

## `termdat_lookup_2.json`

- **Werkzeug:** `termdat_lookup_term` (Abfrage 2 von 2)
- **Endpunkt:** `https://lindas.admin.ch/query`
- **Eingabe:** `{'term': 'Volksschule', 'target_languages': [<TermLanguage.DE: 'de'>, <TermLanguage.FR: 'fr'>, <TermLanguage.IT: 'it'>, <TermLanguage.RM: 'rm'>, <TermLanguage.EN: 'en'>], 'limit': 20}`
- **Aufgezeichnet:** 2026-08-15
- **Groesse:** 9570 B (12 Ergebniszeilen, 1 Treffer im Werkzeug)
- **SHA-256:** `d361d58a413f20bb52160d7013244ad5e15e68f1ddf3e1707a6193066d08a299`
