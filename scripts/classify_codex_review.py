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
from datetime import datetime
from typing import Any

REVIEWED = "reviewed"
PENDING = "pending"
BLOCKED = "blocked"
DRAFT = "draft"

# Der Bot-Login, unter dem Codex sowohl Review-Objekte als auch Issue-Kommentare
# hinterlaesst. GitHub haengt an App-Logins immer "[bot]" an.
CODEX_LOGIN = "chatgpt-codex-connector[bot]"

# Stabile Textmerkmale. Bewusst der Satz *vor* dem wechselnden Schlusssatz:
# «Didn't find any major issues» bleibt, waehrend «Swish!», «Delightful!» und
# «Keep it up!» je nach Lauf wechseln.
MARK_NO_FINDING = "didn't find any major issues"
MARK_QUOTA = "usage limits for code reviews"
MARK_NO_ENVIRONMENT = "create an environment for this repo"


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


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
    head_time = _parse_ts(payload.get("head_committed_at"))

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
    unknown: list[str] = []
    for comment in payload.get("comments") or []:
        if not _is_codex(comment.get("user")):
            continue
        made = _parse_ts(comment.get("created_at"))
        if head_time and made and made < head_time:
            continue  # aelter als der jetzige Head — hat ihn nicht gesehen
        body = (comment.get("body") or "").strip()
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
        unknown.append(body)

    if unknown:
        # Nicht in eine bekannte Schublade zwingen. Die Liste der Gruende ist
        # schon einmal von drei auf vier gewachsen.
        first = unknown[0].replace("\n", " ")[:200]
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

    print(f"state={state}")
    print(f"reason={reason}")

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"state={state}\n")
            fh.write(f"reason={reason}\n")
    # Immer 0: Ueber rot oder gruen entscheidet der Workflow.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
