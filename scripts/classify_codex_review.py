#!/usr/bin/env python3
"""Hat Codex diesen Head geprueft — und wenn nein, warum nicht?

WARUM ES DIESES GATE GIBT
-------------------------
Das PR-Template traegt seit je die Zeile «Codex-Review beantwortet oder behoben
— kein offener Befund beim Merge». Gemessen am 28.8.2026 an drei PRs:

    PR    ready for review   merged     Abstand
    #98   04:27:33           04:27:37   4 s
    #99   04:43:12           04:43:16   4 s
    #62   04:43:33           04:43:36   3 s

In allen drei Faellen kamen `get_reviews` und `get_comments` leer zurueck. Codex
wird beim Umschalten von Draft auf ready ausgeloest und braucht danach Zeit; wer
in derselben Sekunde mergt, hat das Haekchen gesetzt und den Review nicht
abgewartet. Dieselbe Beobachtung steht fuer den 21./22.8. schon in CLAUDE.md.

WARUM KEIN BLOSSER TIMER
------------------------
Ein Gate, das nach N Minuten von selbst gruen wird, behauptet eine Pruefung,
die es nicht gesehen hat. Am 21./22.8. war das Kontingent ueber eine Spanne von
mindestens 25 h weg; ein Timer waere in dieser ganzen Zeit abgelaufen und haette
75 ungeprueften PRs ein gruenes Haekchen gegeben — also genau die falsche
Sicherheit erzeugt, gegen die das Gate gebaut ist. Geprueft wird deshalb, ob
Codex *gesprochen* hat, nicht ob Zeit vergangen ist. Die Wartezeit entsteht als
Nebenwirkung: Solange kein Signal da ist, bleibt das Gate rot.

DIE VIER GRUENDE FUERS SCHWEIGEN
--------------------------------
Aus CLAUDE.md, und nur einer davon ist harmlos:

  reviewed  Review-Objekt mit Befund ODER die Befundlos-Meldung. Beides zaehlt
            als «geprueft» — wer nur das Objekt gelten laesst, zaehlt jeden
            befundlosen Review als ungeprueft.
  draft     Auf Drafts laeuft Codex nicht an. Kein Kommentar ist dort kein
            Beleg, sondern ein nicht durchgefuehrter Test.
  blocked   Kontingent erschoepft oder Environment fehlt. Beides heisst
            ausdruecklich «nicht geprueft» und darf nie gruen werden.
  pending   Noch nichts da. Kann jederzeit in jeden der anderen Zustaende
            kippen.

Ein unbekannter fuenfter Text wird woertlich zitiert statt in eine der
bekannten Schubladen gezwungen: Dieser Abschnitt musste in CLAUDE.md schon
einmal von drei auf vier Gruende wachsen.

DIE FORM TRENNT, NICHT DER ZAEHLER
----------------------------------
Ein Review *mit* Befund ist ein Review-Objekt, ein Review *ohne* Befund und die
beiden Ausfallmeldungen sind gewoehnliche Issue-Kommentare. Das sind zwei
verschiedene Abfragen; wer nur eine nimmt, uebersieht den Rest. `comments: 1`
kann Befundlos-, Kontingent- ODER Environment-Meldung sein — drei
gegensaetzliche Bedeutungen unter derselben Zahl.

DIE SUMMARY-TABELLE (seit 29.8.2026)
------------------------------------
Codex fuehrt seither EINEN Kommentar je PR und schreibt ihn fort — eine Zeile
je Review, mit Status und Commit. Woertlich beobachtet an
swiss-environment-mcp#104, Head `5147312`: um 06:50:52

    | 📝 **Code Review** | 🔄 **Running** since … | `5147312` | Draft marked ready |

und um 06:52:29 derselbe Kommentar mit `✅ **Completed** …`. Der Infokasten sagt
neu: «Codex reacts with 👀 while any review is running, comments if it has
suggestions, and reacts with 👍 once all reviews finish with no findings.» Ein
befundloser Lauf hinterlaesst danach ueberhaupt keinen Text mehr, sondern eine
Reaktion — die Befundlos-Meldung faellt als Signal weg. Ohne die Tabelle bliebe
jeder saubere PR ungruen; an #104 hat das Gate den neuen Kommentar als
unbekannten Text eingeordnet und rot gesetzt, was fuer einen LAUFENDEN Review
schlicht falsch ist.

Die Tabelle ist dabei das bessere Signal als jeder Zeitstempel: Sie nennt den
geprueften Commit selbst. Die Frische einer Summary haengt deshalb an ihrer
Commit-Spalte, nicht an `created_at` — das steht still, waehrend der Kommentar
fortgeschrieben wird, und wuerde nach dem naechsten Push das einzige gueltige
Signal wegfiltern.

Zusammengefuehrt wird nach Schwere: Was ausdruecklich «nicht geprueft» sagt,
schlaegt jede Fertigmeldung. Das Gate darf lieber warten als gruen luegen.

FRISCHE
-------
Ein Review zaehlt nur fuer den Head, den er gesehen hat. Review-Objekte tragen
dafuer `commit_id`. Issue-Kommentare tragen keine Commit-Angabe, also wird ihr
`created_at` gegen den Zeitstempel des Head-Commits gehalten: Ein Kommentar von
vor dem letzten Push hat den jetzigen Stand nicht gesehen.

Aufruf:
    python scripts/classify_codex_review.py --payload gh-payload.json

Gibt `state=...` und `reason=...` auf stdout aus und haengt beides an
`$GITHUB_OUTPUT` an. Der Exit-Code ist immer 0: Ueber rot oder gruen
entscheidet der Workflow, nicht dieser Reporter.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from typing import Any

REVIEWED = "reviewed"
PENDING = "pending"
BLOCKED = "blocked"
DRAFT = "draft"

# Welcher Commit-Status zu welchem Befund gehoert. Die Abbildung steht hier und
# nicht im YAML, weil sie eine Behauptung ist: Sie entscheidet, was ein Mensch
# im PR sieht.
#
# `draft` ist bewusst `pending` und nicht `failure`. Ein Draft ist ohnehin nicht
# mergebar — es gibt nichts aufzuhalten, und «rot» behauptet einen Defekt, den
# es nicht gibt. Gemessen am 28.8.2026 an diesem Gate selbst: Seine ersten
# beiden Laeufe faerbten zwei frische Draft-PRs rot und loesten je ein
# CI-Fehler-Signal aus, obwohl beide genau so waren, wie sie sein sollten. Ein
# Repo, in dem jeder Draft ein rotes Kreuz traegt, bringt seinen Leuten bei,
# rote Kreuze zu uebersehen — und das ist teurer als der Hinweis wert ist.
# `pending` haelt den Merge genauso auf und behauptet dabei nur, was stimmt:
# noch nicht entschieden.
#
# `blocked` bleibt `failure`: Erschoepftes Kontingent und fehlende Environment
# sind kein Wartezustand, sondern brauchen eine Handlung.
COMMIT_STATUS = {
    REVIEWED: "success",
    PENDING: "pending",
    DRAFT: "pending",
    BLOCKED: "failure",
}

# Der Bot-Login, unter dem Codex sowohl Review-Objekte als auch Issue-Kommentare
# hinterlaesst. GitHub haengt an App-Logins immer "[bot]" an.
CODEX_LOGIN = "chatgpt-codex-connector[bot]"

# Stabile Textmerkmale. Bewusst der Satz *vor* dem wechselnden Schlusssatz:
# «Didn't find any major issues» bleibt, waehrend «Swish!», «Delightful!» und
# «Keep it up!» je nach Lauf wechseln.
MARK_NO_FINDING = "didn't find any major issues"
MARK_QUOTA = "usage limits for code reviews"
MARK_NO_ENVIRONMENT = "create an environment for this repo"

# Der fortgeschriebene Sammelkommentar. Der HTML-Marker ist das maschinell
# gemeinte Merkmal und steht im rohen API-Body; manche Zwischenschichten
# schneiden HTML-Kommentare weg, deshalb traegt die Ueberschrift als Rueckfall.
MARK_SUMMARY_HTML = "<!-- codex-pull-request-review-summary -->"
MARK_SUMMARY_HEADING = "## codex review summary"

# Die beiden Statuswoerter, die am 29.8.2026 beobachtet wurden. Bewusst nur
# diese zwei: Ein drittes wird woertlich zitiert statt geraten — dieselbe Regel
# wie beim unbekannten Kommentartext, und aus demselben Grund.
SUMMARY_DONE = "completed"
SUMMARY_RUNNING = "running"

# Rangfolge beim Zusammenfuehren mehrerer Signale. Hoeher schlaegt niedriger.
_SEVERITY = {REVIEWED: 0, PENDING: 1, BLOCKED: 2}

# Rangplatz fuer Kommentare ohne lesbaren Zeitstempel: aelter als alles
# Datierte, damit sie keinen datierten Kommentar ueberstimmen.
_EPOCH = datetime.min.replace(tzinfo=UTC)

# Anhang an die Begruendung, wenn der Anker degradiert ist. Ein stiller
# Rueckfall sieht aus wie ein gesunder Lauf — genau daran ist der 403 aus
# der fehlenden `checks: read`-Permission tagelang unbemerkt geblieben.
_ANKER_DEGRADIERT = (
    " — Achtung: Check-Suites nicht lesbar, die Frische haengt nur am "
    "Committer-Datum. Fehlt dem Workflow `checks: read`?"
)


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_summary(body: str) -> bool:
    low = body.lower()
    return MARK_SUMMARY_HTML in low or MARK_SUMMARY_HEADING in low


def _looks_like_sha(text: str) -> bool:
    # Mindestens sieben Hex-Zeichen. Die Laenge haelt die Kopfzeile («Commit»),
    # die Trennzeile («---») und einen zufaelligen Praefix-Treffer draussen.
    return len(text) >= 7 and all(c in "0123456789abcdef" for c in text.lower())


def _bold_word(cell: str) -> str:
    """Das fettgesetzte Statuswort einer Tabellenzelle, klein geschrieben."""
    start = cell.find("**")
    if start < 0:
        return ""
    end = cell.find("**", start + 2)
    if end < 0:
        return ""
    return cell[start + 2 : end].strip().lower()


def _summary_rows(body: str) -> list[tuple[str, str, str]]:
    """(Commit, Statuswort, Zelle woertlich) je Zeile der Summary-Tabelle."""
    rows: list[tuple[str, str, str]] = []
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 3:
            continue
        commit = cells[2].strip("` ")
        if not _looks_like_sha(commit):
            continue  # Kopf- und Trennzeile fallen genau hier heraus
        rows.append((commit.lower(), _bold_word(cells[1]), cells[1]))
    return rows


def _verdict_from_summary(
    rows: list[tuple[str, str, str]], head_sha: str
) -> tuple[str, str] | None:
    """Urteil aus den Tabellenzeilen, die DIESEN Head nennen."""
    head = head_sha.lower()
    mine = [r for r in rows if head and (head.startswith(r[0]) or r[0].startswith(head))]
    if not mine:
        return None
    kurz = head[:7] or "den Head"
    unbekannt = [r for r in mine if r[1] not in (SUMMARY_DONE, SUMMARY_RUNNING)]
    if unbekannt:
        zelle = unbekannt[0][2].replace("\n", " ")[:200]
        return (
            BLOCKED,
            f"Codex-Summary meldet fuer {kurz} einen unbekannten Status, "
            f"woertlich: «{zelle}» — von Hand einordnen, nicht raten",
        )
    laufend = [r for r in mine if r[1] == SUMMARY_RUNNING]
    if laufend:
        # «once ALL reviews finish»: Solange eine Zeile laeuft, ist der Head
        # nicht fertig geprueft — auch wenn eine andere schon Completed meldet.
        return (
            PENDING,
            f"Codex-Summary: {len(laufend)} von {len(mine)} Review(s) fuer {kurz} laufen noch",
        )
    return (
        REVIEWED,
        f"Codex-Summary meldet {len(mine)} abgeschlossene(n) Review(s) fuer {kurz}",
    )


def _is_codex(author: Any) -> bool:
    if not isinstance(author, dict):
        return False
    return (author.get("login") or "").lower() == CODEX_LOGIN.lower()


def classify(payload: dict[str, Any]) -> tuple[str, str]:
    """(state, reason) aus Reviews, Kommentaren und dem Head-Stand eines PR."""
    if payload.get("draft"):
        return (
            DRAFT,
            "PR ist ein Draft — Codex laeuft darauf nicht an. Auf «ready for "
            "review» stellen; ein kommentarloser Draft ist kein Beleg, sondern "
            "ein nicht durchgefuehrter Test",
        )

    head_sha = payload.get("head_sha") or ""
    # Der Anker fuer die Frische von Kommentaren. `head_committed_at` allein
    # reicht nicht: Es ist das Committer-Datum, nicht der Zeitpunkt, zu dem der
    # Commit PR-Head wurde (Codex-Review vom 28.8.2026, P1). Wer lokal committet
    # (T1), waehrend Codex noch den ALTEN Head befundlos meldet (T2), und erst
    # danach pusht (T3), haette gewonnen: T2 > T1, der Kommentar rutscht durch
    # und markiert einen Stand als geprueft, den Codex nie gesehen hat.
    #
    # `head_seen_at` ist der Zeitpunkt, zu dem GitHub den SHA erstmals gesehen
    # hat: die frueheste Check-Suite auf diesem Commit. Sie entsteht beim Push
    # und haengt an keinem Lauf von uns.
    #
    # Die Laufzeit des Workflows taugt dafuer NICHT (zweiter Codex-Review,
    # 28.8.2026). Ein `issue_comment`-Lauf startet zwangslaeufig NACH dem
    # Kommentar, der ihn ausgeloest hat; ist er der erste, der hier ankommt —
    # weil der `synchronize`-Lauf abgebrochen wurde, und `cancel-in-progress`
    # macht genau das wahrscheinlich —, laege der Anker hinter dem einzigen
    # gueltigen Signal. Das Gate haenge dann dauerhaft auf `pending`. Ein
    # Dauerstall ist schlimmer als die Luecke, die der Anker schliessen soll.
    # `head_seen_at` gilt, wenn es da ist — nicht das spaetere der beiden.
    # `max` sah sicherer aus und oeffnet einen Stall: Ein Commit mit
    # vorgestelltem Committer-Datum (Uhrenversatz, oder von Hand gesetzt) zoege
    # den Anker in die Zukunft, und dann faellt JEDER echte Codex-Kommentar
    # durch die Pruefung — das Gate haengt dauerhaft auf `pending`, obwohl
    # geprueft wurde. Das Committer-Datum ist nur der Rueckfall, wenn keine
    # Beobachtung vorliegt.
    head_time = _parse_ts(payload.get("head_seen_at")) or _parse_ts(
        payload.get("head_committed_at")
    )
    # Nur wenn die Beobachtung gar nicht abrufbar war — nicht, wenn es schlicht
    # keine Check-Suite gibt. Der Hinweis soll auf einen Defekt zeigen, nicht
    # bei jedem Lauf mitlaufen.
    warn = _ANKER_DEGRADIERT if payload.get("head_seen_unavailable") else ""

    # 1) Review-Objekt — traegt eine Commit-Angabe und ist damit eindeutig
    #    einem Stand zuzuordnen.
    for review in payload.get("reviews") or []:
        if not _is_codex(review.get("user")):
            continue
        if head_sha and review.get("commit_id") and review["commit_id"] != head_sha:
            continue  # Review eines aelteren Stands
        return (
            REVIEWED,
            f"Codex-Review-Objekt fuer {head_sha[:7] or 'den Head'} vorhanden "
            f"(state={review.get('state', '?')})",
        )

    # 2) Kommentare. Zwei Sorten, und sie werden verschieden datiert: Die
    #    fortgeschriebene Summary traegt ihren Commit selbst, die uebrigen
    #    Meldungen nur ein `created_at`.
    summary_rows: list[tuple[str, str, str]] = []
    #    Es gewinnt der NEUESTE Treffer, nicht der erste (Codex-Review vom
    #    28.8.2026, P2). `listComments` liefert chronologisch: Kam zuerst die
    #    Kontingent-Meldung und danach — nach einem Retry auf unveraendertem
    #    Head — die Befundlos-Meldung, blieb das Gate sonst rot, obwohl Codex
    #    inzwischen geprueft hatte. Die Gegenrichtung zaehlt genauso: Eine
    #    spaetere Ausfallmeldung darf nicht von einer aelteren Befundlos-Meldung
    #    zugedeckt werden, sonst ist der Fehler nur gespiegelt.
    eligible: list[tuple[datetime, int, str]] = []
    for i, comment in enumerate(payload.get("comments") or []):
        if not _is_codex(comment.get("user")):
            continue
        body = (comment.get("body") or "").strip()
        if _is_summary(body):
            # Kein Zeitfilter: `created_at` bleibt beim ersten Review stehen,
            # waehrend der Kommentar fortgeschrieben wird. Die Commit-Spalte
            # sagt genauer, was geprueft wurde, als jeder Zeitstempel.
            summary_rows.extend(_summary_rows(body))
            continue
        made = _parse_ts(comment.get("created_at"))
        if head_time and made and made < head_time:
            continue  # aelter als der jetzige Head — hat ihn nicht gesehen
        # Ohne Zeitstempel ans Ende der Rangfolge: Ein Kommentar, dessen Alter
        # unbekannt ist, darf keinen datierten ueberstimmen. Die Reihenfolge aus
        # der API bleibt als Tiebreak.
        eligible.append((made or _EPOCH, i, body))

    verdicts = [
        v
        for v in (
            _verdict_from_summary(summary_rows, head_sha),
            _verdict_from_comments(eligible),
        )
        if v
    ]
    if verdicts:
        # Nach Schwere, nicht nach Reihenfolge: Eine Meldung, die ausdruecklich
        # «nicht geprueft» sagt, schlaegt jede Fertigmeldung. Lieber warten als
        # gruen luegen — das ist die ganze These dieses Gates.
        state, reason = max(verdicts, key=lambda v: _SEVERITY[v[0]])
        andere = [v for v in verdicts if v[0] != state]
        if andere:
            reason += f" — daneben: {andere[0][1]}"
        return state, reason + warn

    return (
        PENDING,
        f"Noch kein Codex-Signal fuer {head_sha[:7] or 'den Head'}. Kein "
        "Kommentar heisst nicht «geprueft und sauber»" + warn,
    )


def _verdict_from_comments(
    eligible: list[tuple[datetime, int, str]],
) -> tuple[str, str] | None:
    """Urteil aus den uebrigen Codex-Kommentaren — der neueste gewinnt."""
    if not eligible:
        return None
    _, _, body = max(eligible)
    low = body.lower()
    if MARK_NO_FINDING in low:
        return REVIEWED, "Codex meldet keinen Befund (Befundlos-Meldung)"
    if MARK_QUOTA in low:
        return (
            BLOCKED,
            "Codex-Kontingent fuer Code-Reviews erschoepft — es wurde NICHT "
            "geprueft. Das Kontingent haengt am Konto, nicht am Repo; Stand "
            "im Codex-Dashboard",
        )
    if MARK_NO_ENVIRONMENT in low:
        return (
            BLOCKED,
            "Fuer dieses Repo fehlt eine Codex-Environment — es wurde NICHT "
            "geprueft. Anzulegen je Repo unter "
            "chatgpt.com/codex/cloud/settings/environments",
        )
    # Nicht in eine bekannte Schublade zwingen. Die Liste der Gruende ist
    # schon einmal von drei auf vier gewachsen.
    first = body.replace("\n", " ")[:200]
    return (
        BLOCKED,
        f"Codex hat etwas Unbekanntes gemeldet, woertlich: «{first}» — von "
        "Hand einordnen, nicht raten",
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="classify_codex_review")
    ap.add_argument(
        "--payload",
        default="-",
        help="JSON mit draft/head_sha/head_committed_at/reviews/comments ('-' = stdin)",
    )
    args = ap.parse_args(argv)

    raw = sys.stdin.read() if args.payload == "-" else open(args.payload, encoding="utf-8").read()
    state, reason = classify(json.loads(raw))
    status = COMMIT_STATUS[state]

    print(f"state={state}")
    print(f"status={status}")
    print(f"reason={reason}")

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"state={state}\n")
            fh.write(f"status={status}\n")
            fh.write(f"reason={reason}\n")
    # Immer 0: Ueber rot oder gruen entscheidet der Workflow.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
