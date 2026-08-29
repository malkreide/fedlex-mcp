"""Tests fuer die Einordnung des Codex-Signals (Merge-Gate).

WARUM DIESE DATEI NEBEN DEM SKRIPT LIEGT
----------------------------------------
Aus demselben Grund wie `test_classify_live_run.py`: Der einzige Teil des
Workflows, der etwas *behauptet*, gehoert nicht in einen `run:`-Block, wo ihn
niemand pruefen kann. Der YAML-Teil bleibt duenn — API abfragen, Skript rufen,
Status setzen.

WAS HIER GEPRUEFT WIRD
----------------------
Die Zusicherung ist einzeilig und hart: **Gruen wird nur `reviewed`.** Alles
andere haelt den Merge auf. Die Tests unten belegen jede Grenze dieser Linie
einzeln — besonders die drei Faelle, in denen ein naiver Timer gruen geworden
waere:

  - Draft: Codex laeuft gar nicht an
  - Kontingent erschoepft: am 21./22.8. ueber eine Spanne von mind. 25 h
  - Environment fehlt: kam erst zum Vorschein, als das Kontingent wegfiel

Gegenprobe je Zusicherung: siehe `test_gegenprobe_*`. Sie zeigen, dass die
Trennung nicht zufaellig haelt, sondern an den geprueften Merkmalen haengt.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from classify_codex_review import (  # noqa: E402
    BLOCKED,
    COMMIT_STATUS,
    DRAFT,
    PENDING,
    REVIEWED,
    classify,
)

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "classify_codex_review.py"

HEAD = "b165c905190bede14a1d44435f9a1fa242711265"
T_HEAD = "2026-08-28T04:20:00Z"
T_AFTER = "2026-08-28T04:30:00Z"
T_BEFORE = "2026-08-28T04:10:00Z"

CODEX = {"login": "chatgpt-codex-connector[bot]"}
MENSCH = {"login": "malkreide"}


def _payload(**over):
    base = {
        "draft": False,
        "head_sha": HEAD,
        "head_committed_at": T_HEAD,
        "reviews": [],
        "comments": [],
    }
    base.update(over)
    return base


def _comment(body, user=CODEX, created_at=T_AFTER):
    return {"user": user, "body": body, "created_at": created_at}


# --- Der einzige gruene Fall: reviewed ----------------------------------------


def test_review_objekt_fuer_den_head_zaehlt():
    state, reason = classify(
        _payload(
            reviews=[{"user": CODEX, "commit_id": HEAD, "state": "COMMENTED"}],
        )
    )
    assert state == REVIEWED
    assert HEAD[:7] in reason


def test_befundlos_meldung_zaehlt_als_geprueft():
    """Wer nur das Review-Objekt gelten laesst, zaehlt jeden befundlosen Review
    als ungeprueft — und baut denselben Fehlalarm ein, nur andersherum."""
    state, _ = classify(
        _payload(comments=[_comment("Codex Review: Didn't find any major issues. Swish!")])
    )
    assert state == REVIEWED


@pytest.mark.parametrize(
    "schluss", ["Swish!", "Delightful!", "Keep it up!", "More of your lovely PRs please."]
)
def test_befundlos_erkennt_jeden_schlusssatz(schluss):
    """Der Schlusssatz wechselt bei jedem Lauf; stabil ist nur der Satz davor.

    Haenge die Erkennung an «Swish!», faellt sie beim naechsten Lauf still um.
    """
    state, _ = classify(
        _payload(comments=[_comment(f"Codex Review: Didn't find any major issues. {schluss}")])
    )
    assert state == REVIEWED


# --- Die drei Faelle, in denen ein Timer gruen geworden waere ------------------


def test_draft_ist_kein_beleg():
    state, reason = classify(_payload(draft=True))
    assert state == DRAFT
    assert "nicht durchgefuehrter Test" in reason


def test_kontingent_erschoepft_ist_nicht_geprueft():
    state, reason = classify(
        _payload(comments=[_comment("You have reached your Codex usage limits for code reviews.")])
    )
    assert state == BLOCKED
    assert "NICHT" in reason


def test_fehlende_environment_ist_nicht_geprueft():
    state, reason = classify(
        _payload(comments=[_comment("To use Codex here, create an environment for this repo.")])
    )
    assert state == BLOCKED
    assert "environments" in reason


def test_unbekannter_text_wird_woertlich_zitiert():
    """Die Liste der Gruende ist schon einmal von drei auf vier gewachsen.

    Ein fuenfter Text darf nicht in eine bekannte Schublade gezwungen werden —
    weder in «geprueft» noch in eine der beiden Ausfallmeldungen.
    """
    state, reason = classify(_payload(comments=[_comment("Codex is taking a nap right now.")]))
    assert state == BLOCKED
    assert "taking a nap" in reason
    assert "von Hand einordnen" in reason


def test_gar_kein_signal_ist_pending():
    state, reason = classify(_payload())
    assert state == PENDING
    assert "heisst nicht" in reason


# --- Frische: ein Review gilt nur fuer den Stand, den er gesehen hat -----------


def test_review_eines_aelteren_commits_zaehlt_nicht():
    state, _ = classify(
        _payload(reviews=[{"user": CODEX, "commit_id": "a" * 40, "state": "COMMENTED"}])
    )
    assert state == PENDING


def test_kommentar_von_vor_dem_head_zaehlt_nicht():
    """Issue-Kommentare tragen keine Commit-Angabe — die Zeit muss es richten."""
    state, _ = classify(
        _payload(
            comments=[
                _comment("Didn't find any major issues. Swish!", created_at=T_BEFORE),
            ]
        )
    )
    assert state == PENDING


def test_fremder_kommentar_zaehlt_nicht():
    """Ein Mensch, der «Didn't find any major issues» schreibt, ist kein Review."""
    state, _ = classify(_payload(comments=[_comment("Didn't find any major issues", user=MENSCH)]))
    assert state == PENDING


# --- Gegenproben ---------------------------------------------------------------


def test_gegenprobe_ohne_frischepruefung_waere_der_alte_review_gruen():
    """Belegt, dass `test_review_eines_aelteren_commits_zaehlt_nicht` an der
    Commit-Angabe haengt und nicht daran, dass die Liste leer ist.

    Derselbe Review, nur mit passender Commit-Angabe, wird gruen. Faellt die
    Pruefung auf `commit_id` weg, gehen beide durch — und ein Review von vor
    drei Pushes traegt einen Merge.
    """
    alt = {"user": CODEX, "commit_id": "a" * 40, "state": "COMMENTED"}
    assert classify(_payload(reviews=[alt]))[0] == PENDING
    assert classify(_payload(reviews=[{**alt, "commit_id": HEAD}]))[0] == REVIEWED


def test_gegenprobe_ohne_autorpruefung_waere_jeder_kommentar_gruen():
    """Belegt, dass die Autorpruefung traegt: derselbe Text, nur vom Bot."""
    text = "Didn't find any major issues. Swish!"
    assert classify(_payload(comments=[_comment(text, user=MENSCH)]))[0] == PENDING
    assert classify(_payload(comments=[_comment(text, user=CODEX)]))[0] == REVIEWED


def test_gegenprobe_blocked_ist_nicht_reviewed():
    """Der Kern des Gates: Beide Ausfallmeldungen sind Codex-Kommentare zum
    aktuellen Head. Wer nur «ein Kommentar vom Bot ist da» prueft, macht sie
    gruen — und mergt bei erschoepftem Kontingent ungeprueft weiter."""
    for text in (
        "You have reached your Codex usage limits for code reviews.",
        "To use Codex here, create an environment for this repo.",
    ):
        assert classify(_payload(comments=[_comment(text)]))[0] == BLOCKED


def test_nur_reviewed_ist_gruen():
    """Die Gate-Regel selbst, an einer Stelle festgehalten."""
    assert {REVIEWED, PENDING, BLOCKED, DRAFT} == {"reviewed", "pending", "blocked", "draft"}
    gruen = {REVIEWED}
    assert PENDING not in gruen and BLOCKED not in gruen and DRAFT not in gruen


# --- Der Aufrufweg, den der Workflow nimmt ------------------------------------


def test_cli_schreibt_state_und_reason(tmp_path):
    payload = tmp_path / "p.json"
    payload.write_text(json.dumps(_payload()), encoding="utf-8")
    out = subprocess.run(
        [sys.executable, str(SCRIPT), "--payload", str(payload)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "state=pending" in out.stdout
    assert "reason=" in out.stdout


def test_cli_endet_immer_mit_null(tmp_path):
    """Ueber rot oder gruen entscheidet der Workflow, nicht der Reporter."""
    payload = tmp_path / "p.json"
    payload.write_text(json.dumps(_payload(draft=True)), encoding="utf-8")
    out = subprocess.run(
        [sys.executable, str(SCRIPT), "--payload", str(payload)],
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0
    assert "state=draft" in out.stdout


# --- Welcher Commit-Status zu welchem Befund gehoert --------------------------
#
# Diese Abbildung entscheidet, was ein Mensch im PR sieht, und ist damit eine
# Behauptung — deshalb steht sie im Skript und nicht im YAML.


def test_nur_reviewed_wird_gruen():
    assert COMMIT_STATUS[REVIEWED] == "success"
    for state in (PENDING, DRAFT, BLOCKED):
        assert COMMIT_STATUS[state] != "success"


def test_draft_ist_pending_und_nicht_rot():
    """Gemessen am 28.8.2026 an diesem Gate selbst.

    Seine ersten beiden Laeufe faerbten zwei frische Draft-PRs rot (#101, #64)
    und loesten je ein CI-Fehler-Signal aus — obwohl beide PRs genau so waren,
    wie sie sein sollten. Ein Draft ist ohnehin nicht mergebar; «rot» behauptet
    dort einen Defekt, den es nicht gibt, und ein Repo, in dem jeder Draft ein
    rotes Kreuz traegt, bringt seinen Leuten bei, rote Kreuze zu uebersehen.
    `pending` haelt den Merge genauso auf.
    """
    assert COMMIT_STATUS[DRAFT] == "pending"


def test_blocked_ist_rot_und_nicht_bloss_pending():
    """Gegenstueck zum Test darueber, damit «pending» nicht zur Ausrede wird.

    Erschoepftes Kontingent und fehlende Environment sind kein Wartezustand:
    Ohne Handlung aendert sich daran nichts, also darf es auch nicht so
    aussehen, als warte da jemand.
    """
    assert COMMIT_STATUS[BLOCKED] == "failure"


def test_jeder_zustand_hat_einen_status():
    """Ein fehlender Schluessel wuerde erst im Workflow auffallen — mit einem
    KeyError, der den Status gar nicht erst setzt."""
    assert set(COMMIT_STATUS) == {REVIEWED, PENDING, DRAFT, BLOCKED}
    assert set(COMMIT_STATUS.values()) <= {"success", "pending", "failure", "error"}


def test_cli_gibt_den_status_mit_aus(tmp_path):
    """Der Workflow liest `status=` aus der Ausgabe — fehlt sie, faellt er auf
    `pending` zurueck und ein gruener Lauf wuerde nie gruen."""
    payload = tmp_path / "p.json"
    payload.write_text(
        json.dumps(_payload(reviews=[{"user": CODEX, "commit_id": HEAD, "state": "COMMENTED"}])),
        encoding="utf-8",
    )
    out = subprocess.run(
        [sys.executable, str(SCRIPT), "--payload", str(payload)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "state=reviewed" in out.stdout
    assert "status=success" in out.stdout


def test_cli_gibt_fuer_draft_pending_aus(tmp_path):
    payload = tmp_path / "p.json"
    payload.write_text(json.dumps(_payload(draft=True)), encoding="utf-8")
    out = subprocess.run(
        [sys.executable, str(SCRIPT), "--payload", str(payload)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "state=draft" in out.stdout
    assert "status=pending" in out.stdout


# --- Codex-Review vom 28.8.2026 auf fedlex-mcp#64 -----------------------------
#
# Zwei Befunde am Commit 5d5f033517, beide am Code nachvollzogen und beide echt.
# Sie stehen hier zuerst als fallende Tests, dann kam der Fix — nicht umgekehrt.


def test_p1_kommentar_zwischen_lokalem_commit_und_push_zaehlt_nicht():
    """P1: Die Frische darf nicht am Commit-Datum haengen.

    `head_committed_at` ist das Committer-Datum, nicht der Zeitpunkt, zu dem der
    Commit PR-Head wurde. Wer lokal committet (T1), waehrend Codex noch den
    ALTEN Head befundlos meldet (T2), und erst danach pusht (T3), haette mit der
    alten Regel gewonnen: T2 > T1, der Kommentar rutscht durch — und markiert
    einen Stand als geprueft, den Codex nie gesehen hat.

    `head_seen_at` ist der Zeitpunkt, zu dem wir den SHA erstmals als Head
    gesehen haben (erster eigener `codex-gate`-Status darauf). Der Anker ist das
    spaetere der beiden.
    """
    state, _ = classify(
        _payload(
            head_committed_at="2026-08-28T10:00:00Z",  # T1: lokal committet
            head_seen_at="2026-08-28T12:00:00Z",  # T3: gepusht
            comments=[
                _comment(
                    "Codex Review: Didn't find any major issues. Swish!",
                    created_at="2026-08-28T11:00:00Z",  # T2: galt dem ALTEN Head
                )
            ],
        )
    )
    assert state == PENDING


def test_p1_kommentar_nach_dem_push_zaehlt_weiterhin():
    """Gegenprobe zu P1: Der Anker darf nicht alles wegfiltern."""
    state, _ = classify(
        _payload(
            head_committed_at="2026-08-28T10:00:00Z",
            head_seen_at="2026-08-28T12:00:00Z",
            comments=[
                _comment(
                    "Codex Review: Didn't find any major issues. Swish!",
                    created_at="2026-08-28T12:30:00Z",
                )
            ],
        )
    )
    assert state == REVIEWED


def test_p2_spaetere_befundlos_meldung_schlaegt_aeltere_kontingent_meldung():
    """P2: Nicht der erste Treffer gewinnt, sondern der neueste.

    `listComments` liefert chronologisch. Kam zuerst die Kontingent-Meldung und
    danach — nach einem Retry auf unveraendertem Head — die Befundlos-Meldung,
    blieb das Gate mit der alten Regel rot, obwohl Codex inzwischen geprueft
    hatte.
    """
    state, _ = classify(
        _payload(
            comments=[
                _comment(
                    "You have reached your Codex usage limits for code reviews.",
                    created_at="2026-08-28T12:00:00Z",
                ),
                _comment(
                    "Codex Review: Didn't find any major issues. Swish!",
                    created_at="2026-08-28T12:30:00Z",
                ),
            ]
        )
    )
    assert state == REVIEWED


def test_p2_aeltere_befundlos_meldung_rettet_keine_neuere_kontingent_meldung():
    """Die Gegenrichtung, damit «neuester gewinnt» nicht zur Einbahn wird.

    Ohne diesen Test koennte man P2 auch «befundlos gewinnt immer» loesen — und
    haette den Fehler nur gespiegelt: Ein spaeterer Ausfall waere unsichtbar.
    """
    state, _ = classify(
        _payload(
            comments=[
                _comment(
                    "Codex Review: Didn't find any major issues. Swish!",
                    created_at="2026-08-28T12:00:00Z",
                ),
                _comment(
                    "You have reached your Codex usage limits for code reviews.",
                    created_at="2026-08-28T12:30:00Z",
                ),
            ]
        )
    )
    assert state == BLOCKED


def test_review_objekt_schlaegt_jeden_kommentar():
    """Das Review-Objekt bleibt vorrangig: Es traegt eine Commit-Angabe.

    Ein Kommentar traegt nur einen Zeitstempel; der SHA-Bezug ist das staerkere
    Indiz und wird von «neuester gewinnt» nicht ueberstimmt.
    """
    state, _ = classify(
        _payload(
            reviews=[{"user": CODEX, "commit_id": HEAD, "state": "COMMENTED"}],
            comments=[
                _comment(
                    "You have reached your Codex usage limits for code reviews.",
                    created_at="2026-08-28T23:00:00Z",
                )
            ],
        )
    )
    assert state == REVIEWED


# --- Zweiter Codex-Review, 28.8.2026 auf swiss-environment-mcp#102 ------------
#
# Ein neuer P1, und zwar als direkte Folge des P1-Fixes von vorhin: Der Anker
# durfte nie die Laufzeit des Workflows sein.


def test_p1b_spaeteres_committer_datum_stallt_das_gate_nicht():
    """Der beobachtete Zeitpunkt schlaegt das Committer-Datum, nicht `max`.

    `max(committed, seen)` sah sicherer aus, oeffnet aber einen Stall: Ein
    Commit mit vorgestelltem Committer-Datum (Uhrenversatz, oder von Hand
    gesetzt) zieht den Anker in die Zukunft, und dann faellt JEDER echte
    Codex-Kommentar durch die Frischepruefung — das Gate haengt dauerhaft auf
    `pending`, obwohl geprueft wurde.

    `head_seen_at` stammt aus einer Beobachtung von GitHub (wann der SHA dort
    auftauchte) und ist damit die verlaesslichere Angabe. Sie gilt, wenn sie da
    ist; das Committer-Datum ist nur der Rueckfall.
    """
    state, _ = classify(
        _payload(
            head_committed_at="2027-01-01T00:00:00Z",  # in der Zukunft
            head_seen_at="2026-08-28T12:00:00Z",
            comments=[
                _comment(
                    "Codex Review: Didn't find any major issues. Swish!",
                    created_at="2026-08-28T12:30:00Z",
                )
            ],
        )
    )
    assert state == REVIEWED


def test_p1b_ohne_beobachtung_bleibt_das_committer_datum_der_rueckfall():
    """Gegenprobe: Faellt `head_seen_at` weg, greift wieder das Committer-Datum.

    Sonst waere die Frischepruefung bei fehlender Beobachtung ganz aus — und
    ein Kommentar zum alten Head koennte den neuen gruen faerben.
    """
    state, _ = classify(
        _payload(
            head_committed_at="2026-08-28T12:00:00Z",
            head_seen_at=None,
            comments=[
                _comment(
                    "Codex Review: Didn't find any major issues. Swish!",
                    created_at="2026-08-28T11:00:00Z",
                )
            ],
        )
    )
    assert state == PENDING


# --- Dritter Codex-Review, 28.8.2026 auf fedlex-mcp#66 ------------------------
#
# Der Befund war kein Denkfehler am Anker, sondern eine fehlende Permission:
# Der explizite `permissions`-Block nannte kein `checks`, GitHub setzt jeden
# nicht genannten Scope auf `none`, und `listSuitesForRef` braucht `checks:
# read`. Der 403 landete im `catch`, `head_seen_at` blieb leer — und die Frische
# fiel still auf das Committer-Datum zurueck, also in die Luecke von Runde 1.
#
# Die Permission steht im Workflow und ist von hier aus nicht pruefbar. Was
# hier geprueft wird, ist der Grund, warum der Fehler ueberhaupt so lange
# unsichtbar war: Ein stiller Rueckfall sieht aus wie ein gesunder Lauf.


def test_unlesbare_check_suites_stehen_in_der_begruendung():
    """Ein degradierter Anker muss man dem Status ansehen.

    Sonst meldet das Gate «noch kein Signal» und verschweigt, dass es gerade
    mit der schwaecheren Frischepruefung arbeitet — genau die Sorte Meldung,
    die diese ganze Sitzung teuer gemacht hat.
    """
    state, reason = classify(_payload(head_seen_unavailable=True))

    assert state == PENDING
    assert "checks: read" in reason


def test_ohne_stoerung_keine_warnung_in_der_begruendung():
    """Gegenprobe: Der Hinweis darf nicht im Normalfall mitlaufen.

    Eine Warnung, die immer dasteht, liest nach der dritten Woche niemand mehr.
    """
    _, reason = classify(_payload())
    assert "checks: read" not in reason


def test_warnung_auch_bei_einem_kommentar_basierten_urteil():
    """Der Hinweis haengt an der Frischepruefung, nicht am Zustand.

    Gerade das gruene Urteil ist der Fall, in dem der degradierte Anker
    schaedlich waere — dort muss er sichtbar sein.
    """
    _, reason = classify(
        _payload(
            head_seen_unavailable=True,
            comments=[_comment("Codex Review: Didn't find any major issues. Swish!")],
        )
    )
    assert "checks: read" in reason


def test_review_objekt_braucht_die_warnung_nicht():
    """Ein Review-Objekt haengt am SHA, nicht am Zeitstempel — dort ist der
    Anker gleichgueltig, und ein Hinweis waere nur Rauschen."""
    _, reason = classify(
        _payload(
            head_seen_unavailable=True,
            reviews=[{"user": CODEX, "commit_id": HEAD, "state": "COMMENTED"}],
        )
    )
    assert "checks: read" not in reason


# --- Codex hat am 29.8.2026 das Meldeformat gewechselt ------------------------
#
# Statt einer Befundlos-Meldung im Fliesstext schreibt Codex jetzt EINEN
# Kommentar, den es in Ort und Stelle fortschreibt: eine Tabelle je Review, mit
# Status und Commit. Woertlich beobachtet an swiss-environment-mcp#104, Head
# `5147312` — erst
#
#     | 📝 **Code Review** | 🔄 **Running** since 2026-08-29T06:50:41… | `5147312` | …
#
# um 06:50:52, dann um 06:52:29 derselbe Kommentar mit
#
#     | 📝 **Code Review** | ✅ **Completed** 2026-08-29T06:52:26.201705Z | `5147312` | …
#
# Der Infokasten sagt dazu neu: «Codex reacts with 👀 while any review is
# running, comments if it has suggestions, and reacts with 👍 once all reviews
# finish with no findings.» Ein befundloser Lauf hinterlaesst danach gar keinen
# Text mehr, sondern eine Reaktion — die alte Befundlos-Meldung faellt als
# Signal weg. Ohne die Tabelle bliebe jeder saubere PR ungruen; das Gate hat
# den neuen Kommentar an #104 als unbekannten Text eingeordnet und rot gesetzt.
#
# Die Tabelle ist dafuer das bessere Signal als jeder Zeitstempel: Sie nennt den
# geprueften Commit selbst. Deshalb haengt die Frische einer Summary an ihrer
# Commit-Spalte und nicht an `created_at` — letzteres steht ohnehin still,
# waehrend der Kommentar fortgeschrieben wird.

SUMMARY_MARKER = "<!-- codex-pull-request-review-summary -->"


def _summary(status_cell, commit="b165c90", name="\U0001f4dd **Code Review**", marker=True):
    """Der Sammelkommentar, aufgezeichnet statt nachgebaut.

    Woertlich aus dem Webhook zu `fedlex-mcp#67` vom 29.8.2026, 06:51:36 UTC —
    inklusive `<details>`-Huelle und `<relative-time>`-Element in der
    Statuszelle. Die Fassung, die ueber die MCP-Abfrage kam, war davon
    HTML-bereinigt; wer nur die nachbaut, prueft seine eigene Annahme statt der
    Quelle. Beide Formen muessen durchgehen, siehe
    `test_summary_auch_in_der_html_bereinigten_fassung`.
    """
    kopf = SUMMARY_MARKER + "\n\n" if marker else ""
    return (
        f"{kopf}## Codex Review Summary\n\n"
        "This comment shows the latest Codex review activity on this pull request.\n\n"
        "| Review | Status | Commit | Review trigger |\n"
        "| --- | --- | --- | --- |\n"
        f"| {name} | {status_cell} | `{commit}` | Draft marked ready |\n\n\n\n"
        "<details> <summary>\u2139\ufe0f About Codex in GitHub</summary>\n<br/>\n\n"
        "[Your team has set up Codex to review pull requests in this repo]"
        "(https://chatgpt.com/codex/cloud/settings/general). Reviews are triggered "
        "when you\n- Open a pull request for review\n- Mark a draft as ready\n"
        '- Comment "@codex review" or "@codex security review".\n\n'
        "Codex reacts with \U0001f440 while any review is running, comments if it has "
        "suggestions, and reacts with \U0001f44d once all reviews finish with no "
        "findings.\n\n</details>"
    )


def _zeit(iso):
    """Die Statuszelle traegt den Zeitpunkt als HTML-Element, nicht als Text."""
    return f'<relative-time datetime="{iso}">{iso}</relative-time>'


FERTIG = "\u2705 **Completed** " + _zeit("2026-08-29T06:52:26.201705Z")
LAEUFT = "\U0001f504 **Running** since " + _zeit("2026-08-29T06:51:31.539632Z")


def test_summary_completed_fuer_den_head_zaehlt_als_geprueft():
    state, reason = classify(_payload(comments=[_comment(_summary(FERTIG))]))
    assert state == REVIEWED
    assert "Summary" in reason


def test_summary_running_ist_pending_und_kein_ausfall():
    # Ein laufender Review ist kein erschoepftes Kontingent. Genau diese
    # Verwechslung hat das Gate an #104 rot gemacht.
    state, _ = classify(_payload(comments=[_comment(_summary(LAEUFT))]))
    assert state == PENDING


def test_summary_auch_in_der_html_bereinigten_fassung():
    # Ueber die MCP-Abfrage kam derselbe Kommentar ohne `<relative-time>` und
    # ohne `<details>`. Welche Zwischenschicht was wegschneidet, ist nicht
    # unsere Sache — die Einordnung darf an keiner der beiden Formen haengen.
    bereinigt = _summary(FERTIG).replace(
        _zeit("2026-08-29T06:52:26.201705Z"), "2026-08-29T06:52:26.201705Z"
    )
    bereinigt = bereinigt.replace("<details> <summary>", " ").replace("</summary>", "")
    bereinigt = bereinigt.replace("</details>", "")
    assert "<relative-time" not in bereinigt and "<details" not in bereinigt
    state, _ = classify(_payload(comments=[_comment(bereinigt)]))
    assert state == REVIEWED


def test_summary_wird_auch_ohne_html_marker_erkannt():
    # Der rohe API-Body traegt den Marker; manche Zwischenschichten schneiden
    # HTML-Kommentare weg. Die Ueberschrift traegt dann allein.
    state, _ = classify(_payload(comments=[_comment(_summary(FERTIG, marker=False))]))
    assert state == REVIEWED


def test_summary_fuer_einen_anderen_commit_zaehlt_nicht():
    state, _ = classify(_payload(comments=[_comment(_summary(FERTIG, commit="deadbee"))]))
    assert state == PENDING


def test_summary_zaehlt_trotz_alten_erstellungsdatums():
    # Der Kommentar wird fortgeschrieben: `created_at` bleibt beim ERSTEN
    # Review stehen, waehrend die Tabelle den jetzigen Head meldet. Wer hier
    # nach Zeit filtert, wirft das einzige gueltige Signal weg.
    state, _ = classify(_payload(comments=[_comment(_summary(FERTIG), created_at=T_BEFORE)]))
    assert state == REVIEWED


def test_summary_mit_unbekanntem_status_wird_woertlich_zitiert():
    state, reason = classify(_payload(comments=[_comment(_summary("💥 **Errored** irgendwas"))]))
    assert state == BLOCKED
    assert "Errored" in reason


def test_summary_ein_laufender_review_haelt_die_fertigen_auf():
    body = _summary(FERTIG).replace(
        "| Draft marked ready |\n",
        "| Draft marked ready |\n| 🔒 **Security Review** | "
        + LAEUFT
        + " | `b165c90` | Draft marked ready |\n",
    )
    state, _ = classify(_payload(comments=[_comment(body)]))
    assert state == PENDING


def test_summary_verdeckt_keine_kontingent_meldung():
    # Zusammengefuehrt wird nach Schwere, nicht nach Reihenfolge: Was
    # ausdruecklich «nicht geprueft» sagt, darf kein gruenes Haekchen bekommen.
    state, _ = classify(
        _payload(
            comments=[
                _comment(_summary(FERTIG)),
                _comment("You have reached your Codex usage limits for code reviews."),
            ]
        )
    )
    assert state == BLOCKED


def test_gegenprobe_ohne_commit_spalte_waere_jede_summary_gruen():
    # Haengt die Frische wirklich an der Commit-Spalte? Dann muss eine Summary,
    # die einen fremden Commit meldet, das Gate NICHT gruen machen — und eine
    # mit dem Head sehr wohl.
    fremd, _ = classify(_payload(comments=[_comment(_summary(FERTIG, commit="0000000"))]))
    eigen, _ = classify(_payload(comments=[_comment(_summary(FERTIG))]))
    assert (fremd, eigen) == (PENDING, REVIEWED)


# --- Der Auslöser muss zum fortgeschriebenen Kommentar passen -----------------


def test_gate_hoert_auch_auf_bearbeitete_kommentare():
    # Seit dem 29.8.2026 wechselt das Signal von «Running» auf «Completed»
    # durch eine BEARBEITUNG desselben Kommentars, nicht durch einen neuen.
    # `issue_comment: [created]` allein sieht diesen Wechsel nie. Der Poll-Lauf
    # faengt ihn nur, solange sein Zeitfenster laeuft — danach bliebe das Gate
    # auf `pending` stehen, obwohl Codex laengst fertig ist.
    yml = (Path(__file__).resolve().parents[1] / ".github/workflows/codex-gate.yml").read_text(
        encoding="utf-8"
    )
    block = yml.split("issue_comment:", 1)[1].split("\n\n", 1)[0]
    assert "edited" in block, (
        "Der Wechsel Running -> Completed ist eine Bearbeitung; ohne `edited` "
        "sieht das Gate ihn nach Ablauf des Poll-Fensters nicht mehr"
    )
