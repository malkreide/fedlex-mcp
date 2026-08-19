#!/usr/bin/env bash
#
# SessionStart: Klon-Aktualitaet melden.
#
# WARUM (siehe auch .claude/hooks/README.md):
# Ein veralteter Klon hat am 3.8.2026 zweimal eine rote CI erzeugt, deren
# Ursache nicht im Diff stand -- die fehlenden Commits waren jeweils genau
# die, die das Gate einfuehrten, an dem der Branch scheiterte. Die Pruefung
# kostet eine Sekunde und ersetzt eine Fehlersuche in den falschen Dateien.
#
# OBERSTE REGEL: Dieser Hook blockiert die Session NIEMALS.
# Kein Netz, kein Remote, detached HEAD, flatterndes DNS, fehlendes git,
# fehlendes `timeout` -- jeder dieser Faelle geht still durch, Exit 0.
# Ein Hook, der bei Netzproblemen die Arbeit anhaelt, wird nach dem zweiten
# Mal abgeschaltet und schuetzt danach gar nichts.
#
# Deshalb bewusst KEIN `set -e` / `set -o pipefail`: ein fehlschlagender
# Teilschritt soll hier weiterlaufen und am Ende schweigen, nicht abbrechen.

# Gesamtbudget fuer alle Netz-Aufrufe zusammen, in Sekunden.
BUDGET=${CLAUDE_STALENESS_TIMEOUT:-6}
SECONDS=0

# `timeout` ist die einzige Garantie gegen ein haengendes fetch. Ohne sie
# lieber gar nicht pruefen als den Sessionstart riskieren.
command -v timeout >/dev/null 2>&1 || exit 0
command -v git     >/dev/null 2>&1 || exit 0

cd "${CLAUDE_PROJECT_DIR:-$PWD}" 2>/dev/null || exit 0
[ "$(git rev-parse --is-inside-work-tree 2>/dev/null)" = "true" ] || exit 0

# Unborn HEAD (frisch initialisiertes Repo): nichts zu vergleichen.
git rev-parse --verify --quiet HEAD >/dev/null 2>&1 || exit 0
git remote get-url origin >/dev/null 2>&1 || exit 0

# Nichts darf interaktiv nachfragen -- ein Credential-Prompt haengt
# unsichtbar bis zum Timeout und ist die haeufigste Hoernerfalle.
export GIT_TERMINAL_PROMPT=0
export GIT_ASKPASS=/bin/true
export SSH_ASKPASS=/bin/true
export GIT_SSH_COMMAND="${GIT_SSH_COMMAND:-ssh -oBatchMode=yes -oConnectTimeout=3}"
export GIT_CONFIG_PARAMETERS="'credential.helper='"

# Restbudget in ganzen Sekunden; leer, wenn das Budget aufgebraucht ist.
remaining() {
  local r=$(( BUDGET - SECONDS ))
  [ "$r" -ge 1 ] || return 1
  printf '%s' "$r"
}

# Standard-Branch ERMITTELN, nicht "main" annehmen: mindestens ein Repo im
# Portfolio nutzt "master", und genau diese Annahme hat schon einmal einen
# Branch 15 Commits alt werden lassen.
# Schritt 1 ist der lokale Cache -- kostenlos und ohne Netz.
default_branch=$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null)
default_branch=${default_branch#origin/}

# Schritt 2: Remote fragen, aber nur mit Timeout.
if [ -z "$default_branch" ]; then
  t=$(remaining) || exit 0
  default_branch=$(timeout "$t" git ls-remote --symref origin HEAD 2>/dev/null |
    sed -n 's|^ref: refs/heads/\([^[:space:]]*\).*|\1|p' | head -1)
fi

# Kein Standard-Branch ermittelbar -> schweigen. Kein Raten, kein Fallback
# auf "main": ein geratener Branch misst die falsche Distanz oder scheitert
# mit "couldn't find remote ref", was wie ein Netzproblem aussieht.
[ -n "$default_branch" ] || exit 0

t=$(remaining) || exit 0
timeout "$t" git fetch --quiet origin "refs/heads/${default_branch}" >/dev/null 2>&1 || exit 0

behind=$(git rev-list --count HEAD..FETCH_HEAD 2>/dev/null)

# Nur melden, wenn tatsaechlich Commits fehlen. Bei 0 schweigt der Hook.
case "$behind" in
  ''|*[!0-9]*) exit 0 ;;
  0)           exit 0 ;;
esac

current=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
[ "$current" = "HEAD" ] && current="detached HEAD"

printf 'Klon-Aktualitaet: Der ausgecheckte Stand (%s) liegt %s Commit(s) hinter origin/%s.\n' \
  "$current" "$behind" "$default_branch"
printf 'Erfahrungswert aus diesem Portfolio: fehlende Basis-Commits erzeugen eine rote CI,\n'
printf 'deren Ursache nicht im Diff steht -- es fehlt das Gate, an dem der Branch scheitert.\n'
printf 'Vor dem Debuggen einer roten CI zuerst: git merge origin/%s (bzw. rebase).\n' \
  "$default_branch"

exit 0
