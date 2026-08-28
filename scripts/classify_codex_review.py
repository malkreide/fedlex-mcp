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

# Rangplatz fuer Kommentare ohne lesbaren Zeitstempel: aelter als alles
# Datierte, damit sie keinen datierten Kommentar ueberstimmen.
_EPOCH = datetime.min.replace(tzinfo=UTC)


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _latest(*times: datetime | None) -> datetime | None:
    """Der spaeteste der uebergebenen Zeitpunkte, oder None wenn keiner da ist."""
    known = [t for t in times if t is not None]
    return max(known) if known else None


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
    # `head_seen_at` ist der Zeitpunkt, zu dem wir den SHA erstmals als Head
    # gesehen haben — der erste eigene `codex-gate`-Status darauf, gesetzt vom
    # Lauf, den der Push ausgeloest hat. Das spaetere der beiden gilt.
    head_time = _latest(
        _parse_ts(payload.get("head_committed_at")),
        _parse_ts(payload.get("head_seen_at")),
    )

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

    # 2) Gewoehnliche Issue-Kommentare — drei bekannte Bedeutungen, und eine
    #    vierte Moeglichkeit, die woertlich weitergereicht wird.
    #
    #    Es gewinnt der NEUESTE, nicht der erste Treffer (Codex-Review vom
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
        made = _parse_ts(comment.get("created_at"))
        if head_time and made and made < head_time:
            continue  # aelter als der jetzige Head — hat ihn nicht gesehen
        # Ohne Zeitstempel ans Ende der Rangfolge: Ein Kommentar, dessen Alter
        # unbekannt ist, darf keinen datierten ueberstimmen. Die Reihenfolge aus
        # der API bleibt als Tiebreak.
        eligible.append((made or _EPOCH, i, (comment.get("body") or "").strip()))

    if eligible:
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

    return (
        PENDING,
        f"Noch kein Codex-Signal fuer {head_sha[:7] or 'den Head'}. Kein "
        "Kommentar heisst nicht «geprueft und sauber»",
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
