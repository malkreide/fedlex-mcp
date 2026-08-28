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
