# SessionStart-Hook: Klon-Aktualität

`session-start.sh` meldet beim Sessionstart, wie viele Commits der
ausgecheckte Stand hinter `origin/<default-branch>` liegt. Registriert in
`.claude/settings.json` unter `hooks.SessionStart`.

## Grund

Ein veralteter Klon hat am 3.8.2026 **zweimal** eine rote CI erzeugt, deren
Ursache nicht im Diff stand — die fehlenden Commits waren jeweils genau die,
die das Gate einführten, an dem der Branch scheiterte. Man sucht den Fehler
dann in den geänderten Dateien, wo er nicht ist. Die Prüfung kostet eine
Sekunde und ersetzt eine Fehlersuche in den falschen Dateien.

Das ist die maschinelle Variante des Absatzes «Vor der Arbeit» in
`CLAUDE.md`: dort steht dieselbe Prüfung als Handgriff, den man vergisst.

## Verhalten

| Situation | Verhalten |
|---|---|
| Stand ist aktuell (0 Commits zurück) | **schweigt** — keine Ausgabe |
| Stand liegt N > 0 Commits zurück | meldet N, Branch, Standard-Branch und den Fix |
| Kein Netz, DNS flattert, Remote weg | still, Exit 0 |
| Kein `origin`, kein Git-Repo, kein `git` | still, Exit 0 |
| Detached HEAD | funktioniert (meldet «detached HEAD» als Stand) |
| Unborn HEAD (frisches Repo ohne Commit) | still, Exit 0 |
| `timeout` nicht im `PATH` | still, Exit 0 — siehe unten |

Der Hook **blockiert die Session unter keinen Umständen** und endet immer
mit Exit 0. Das ist Anforderung Nummer eins, nicht eine Politur: ein Hook,
der bei Netzproblemen die Arbeit anhält, wird nach dem zweiten Mal
abgeschaltet und schützt danach gar nichts.

## Warum die Konstruktion so aussieht

**Kein `set -e`.** Bewusst. Fast jeder Schritt hier darf fehlschlagen; der
richtige Umgang damit ist schweigen und weiterlaufen, nicht abbrechen.

**Der Standard-Branch wird ermittelt, nicht angenommen.** Drei Server im
Portfolio heissen ihren Standard-Branch `master`. Ein fest verdrahtetes
`main` misst entweder die falsche Distanz oder scheitert mit «couldn't find
remote ref main» — was wie ein Netzproblem aussieht und deshalb ignoriert
wird, während der Klon weiter altert. Zuerst wird der lokale Cache
`refs/remotes/origin/HEAD` gelesen (kostenlos, kein Netz), erst danach
`git ls-remote --symref origin HEAD` gefragt. Lässt sich der Branch nicht
ermitteln, schweigt der Hook — geraten wird nicht.

**Ohne `timeout` läuft die Prüfung gar nicht.** `timeout` ist die einzige
harte Garantie gegen ein hängendes `fetch`. Fehlt es (etwa macOS ohne
coreutils), ist «nicht prüfen» die richtige Antwort, nicht «ungeschützt
prüfen».

**Alles Interaktive ist abgeschaltet** (`GIT_TERMINAL_PROMPT=0`,
`GIT_ASKPASS`, `credential.helper=` leer, `ssh -oBatchMode=yes`). Ein
Credential-Prompt hängt sonst unsichtbar bis zum Timeout — der häufigste
Weg, wie ein «schneller» Netzaufruf zur Wartezeit wird.

**Der `fetch` fasst nichts Lokales an.** Der Vergleich läuft über
`FETCH_HEAD`. Nebenbei aktualisiert git dabei — wegen der Standard-Refspec
`+refs/heads/*:refs/remotes/origin/*` — auch `refs/remotes/origin/<branch>`
per Fast-Forward; das tut jedes gewöhnliche `git fetch` ebenso und ist
erwünscht, weil es den lokalen Cache für den nächsten Lauf füllt. **Lokale
Branches, der Index und das Arbeitsverzeichnis bleiben unberührt** — der Hook
merged, rebased und checkoutet nichts.

## Budget

Ein gemeinsames Budget für *alle* Netzaufrufe zusammen, Standard 6 Sekunden,
über `CLAUDE_STALENESS_TIMEOUT` überschreibbar. Reicht das Restbudget nicht
mehr für den nächsten Aufruf, bricht der Hook still ab. Worst case ist damit
das Budget, nicht ein Vielfaches davon.

```bash
CLAUDE_STALENESS_TIMEOUT=10 .claude/hooks/session-start.sh
```

## Manuell testen

```bash
# Normalfall
.claude/hooks/session-start.sh; echo "exit=$?"

# Erzwungener Rückstand (muss melden)
git -C "$(mktemp -d)" ... # oder einfach: git checkout HEAD~3 && .claude/hooks/session-start.sh

# Kein Netz (muss schweigen, exit=0)
CLAUDE_STALENESS_TIMEOUT=1 https_proxy=http://127.0.0.1:1 \
  .claude/hooks/session-start.sh; echo "exit=$?"
```
