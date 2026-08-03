"""
swiss-mcp-commons — wiederverwendbarer SPARQL-/JSON-Client mit Retry.

VENDORED COPY (v1.1.0). Dieses Modul wird **byte-identisch** in mehreren
`*-mcp`-Servern des Portfolios vorgehalten (aktuell `swiss-environment-mcp` und
`fedlex-mcp`). Kanonische Quelle ist genau diese Datei — Änderungen hier und in
den Schwesterkopien **synchron** halten, bis ein installierbares Paket
`swiss-mcp-commons` (PyPI/OIDC Trusted Publisher) existiert; dann ersetzt der
Paket-Import diese Kopien.

Das Modul kapselt den gemeinsamen Client-Aufbau (ursprünglich aus `fedlex-mcp`,
`_execute_sparql`): GET mit `format=application/sparql-results+json`, Retry
ausschliesslich bei transienten Fehlern (429/5xx, Timeout/Netzwerk) mit
exponentiellem Backoff, deterministische 4xx sofort durchgereicht.

**Bewusst abhängigkeitsarm** (nur `httpx`, `asyncio`) und ohne Bezug auf
server-spezifische Egress-/Client-/Logging-Details — der Egress-Guard und das
Retry-Logging werden als optionale Callbacks übergeben, der HTTP-Client vom
Aufrufer. Damit bleibt das Modul 1:1 in ein gemeinsames Paket hebbar.
"""

import asyncio
import random
import time
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

# Transiente HTTP-Status → Retry. 4xx (ausser 429) sind deterministisch.
RETRYABLE_STATUS: frozenset[int] = frozenset({429, 502, 503, 504})
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BASE_DELAY = 0.5  # Sekunden; exp. Backoff base*2**attempt. Tests: 0.

# --- Retry-Politik (ARCH-014) ------------------------------------------------
# *Was* wiederholt wird, steht in RETRYABLE_STATUS. Diese Konstanten regeln
# *wie schnell* und *wie lange*.

#: Deckel auf eine einzelne Wartezeit — gegen die unbegrenzt wachsende Leiter
#: und gegen ein ``Retry-After``, das der Endpoint senden darf, das man aber
#: nicht absitzen muss.
MAX_DELAY_S = 20.0

#: Streuung. Ohne sie wiederholen alle Clients, die denselben Ausfall getroffen
#: haben, im Gleichtakt — die Last kommt als Welle zurueck, genau wenn der
#: Endpoint sich erholt.
JITTER_SPREAD = 0.5  # exponentielle Wartezeiten landen in [0.5x, 1.5x]

#: Auf einem ``Retry-After`` ist die Streuung einseitig: spaeter ist hoeflich,
#: frueher missachtet genau den Wert, den man gerade gelesen hat.
RETRY_AFTER_JITTER = 0.25  # landet in [1.0x, 1.25x]

#: Statuscodes, die ein sinnvolles ``Retry-After`` tragen (RFC 9110 §10.2.3).
RETRY_AFTER_STATUSES = frozenset({429, 503})

#: Deckel auf den *ganzen* Aufruf — alle Versuche und Wartezeiten zusammen.
#:
#: Eine Anzahl Versuche ist keine Grenze: Drei Versuche a 45 s plus Backoff sind
#: ueber zwei Minuten, und ``DEFAULT_MAX_ATTEMPTS = 3`` sagt das nirgends.
#:
#: **Der Wert liegt bewusst ueber dem MCP-Client-Default.** Das Python-SDK setzt
#: ``MCP_DEFAULT_TIMEOUT = 30.0``; Schwester-Server mit festen Dumps
#: (``swiss-efv-mcp``, ``termdat-mcp``) bleiben mit 25 s darunter. Hier gilt die
#: Ausnahme wie bei ``lindas-mcp`` und ``parlament-mcp``: Beide Endpoints sind
#: SPARQL und stehen mit ``REQUEST_TIMEOUT``/``LINDAS_TIMEOUT`` bei 45 s. Ein
#: Budget unter 30 s wuerde legitime Queries abwuergen, die heute durchkommen.
#:
#: Die Folge ist angenommen, nicht uebersehen: Ein Aufrufer mit SDK-Default kann
#: aufgeben, bevor eine langsame Query zurueckkommt.
TOTAL_BUDGET_S = 45.0


def parse_retry_after(resp: httpx.Response | None) -> float | None:
    """Sekunden laut ``Retry-After`` der Antwort, oder None.

    RFC 9110 §10.2.3 erlaubt zwei Formen: Sekundenzahl und HTTP-Datum. Beide
    kommen vor, beide werden gelesen. Unbrauchbares ergibt None, und der
    Aufrufer faellt auf seine eigene Kurve zurueck — eine kaputte Kopfzeile darf
    auf dem Fehlerpfad nicht zum Absturz werden.
    """
    if resp is None or resp.status_code not in RETRY_AFTER_STATUSES:
        return None
    raw = (resp.headers.get("Retry-After") or "").strip()
    if not raw:
        return None
    if raw.isdigit():
        return float(raw)
    try:
        when = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if when is None:
        return None
    if when.tzinfo is None:  # RFC-9110-Daten sind GMT; naiv heisst UTC
        when = when.replace(tzinfo=UTC)
    return max(0.0, (when - datetime.now(UTC)).total_seconds())


def retry_delay(attempt: int, last_error: Exception | None, base_delay: float) -> float:
    """Sekunden Wartezeit nach dem fehlgeschlagenen ``attempt``.

    Die Antwort des Endpoints schlaegt unsere Vermutung: Ein ``Retry-After`` bei
    429 oder 503 gewinnt gegen die Exponentialkurve, die dieselbe Frage nur raet.
    """
    hinted = parse_retry_after(getattr(last_error, "response", None))
    if hinted is not None:
        jittered = hinted * (1.0 + random.random() * RETRY_AFTER_JITTER)
    else:
        jittered = (base_delay * (2**attempt)) * (
            1.0 - JITTER_SPREAD + random.random() * 2 * JITTER_SPREAD
        )
    # Cap *after* jitter. The other order made MAX_DELAY_S not a bound at all:
    # a value capped at 20s was then multiplied by up to 1.5 and landed at 30s.
    return min(jittered, MAX_DELAY_S)


def sparql_escape(value: str) -> str:
    """Escaped einen String für die sichere Interpolation in ein SPARQL-Literal.

    Verhindert das Ausbrechen aus doppelt-gequoteten Literalen (Defense-in-Depth
    zusätzlich zur Eingabe-Validierung).
    """
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def binding_val(binding: dict[str, Any], key: str, default: str = "") -> str:
    """Extrahiert sicher den String-Wert aus einem SPARQL-Result-Binding."""
    entry = binding.get(key)
    return entry.get("value", default) if entry else default


async def _request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    params: dict[str, Any] | None,
    headers: dict[str, str] | None,
    base_delay: float,
    max_attempts: int,
    egress_check: Callable[[str], None] | None,
    on_retry: Callable[[int, str, Exception], None] | None,
    total_budget: float = TOTAL_BUDGET_S,
) -> httpx.Response:
    """Gemeinsamer Retry-Kern für GET-Requests (SPARQL + JSON)."""
    if egress_check is not None:
        egress_check(url)
    # ARCH-014: Das Budget begrenzt den ganzen Aufruf, nicht nur eine Wartezeit.
    # Monotone Uhr, damit ein NTP-Sprung kein Budget verteilt oder einzieht.
    deadline = time.monotonic() + total_budget
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            # httpx wendet sein Timeout pro Operation an (connect/read/write/
            # pool), und das Read-Timeout beginnt mit jedem Chunk von vorn — das
            # begrenzt jeden Schritt, nicht den Aufruf. Eine langsam
            # troepfelnde Antwort koennte das Budget also ueberdauern.
            # `asyncio.timeout` ist die Wanduhr-Deadline, die das Budget
            # tatsaechlich verspricht; das httpx-Timeout bleibt als feinere
            # Grenze pro Operation daneben.
            async with asyncio.timeout(remaining):
                response = await client.request(
                    method, url, params=params, headers=headers, timeout=remaining
                )
                response.raise_for_status()
                return response
        except TimeoutError as e:  # Budget aufgebraucht, nicht bloss dieser Versuch
            last_exc = e
            break
        except httpx.HTTPStatusError as e:
            if e.response.status_code not in RETRYABLE_STATUS:
                raise
            last_exc = e
        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as e:
            last_exc = e
        if attempt < max_attempts - 1:
            delay = retry_delay(attempt, last_exc, base_delay)
            # Eine Wartezeit, die das Budget ueberdauert, ist eine Wartezeit fuer
            # niemanden: Der Aufrufer hat aufgegeben, bevor sie endet.
            if delay >= deadline - time.monotonic():
                break
            if on_retry is not None:
                on_retry(attempt + 1, url, last_exc)
            await asyncio.sleep(delay)
    assert last_exc is not None  # pragma: no cover - Schleife garantiert gesetzt
    raise last_exc


async def get_bindings(
    client: httpx.AsyncClient,
    endpoint: str,
    query: str,
    *,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    egress_check: Callable[[str], None] | None = None,
    on_retry: Callable[[int, str, Exception], None] | None = None,
) -> list[dict[str, Any]]:
    """Führt eine SPARQL-Abfrage aus und liefert die Result-Bindings."""
    params = {"query": query, "format": "application/sparql-results+json"}
    headers = {"Accept": "application/sparql-results+json"}
    response = await _request_with_retry(
        client,
        "GET",
        endpoint,
        params=params,
        headers=headers,
        base_delay=base_delay,
        max_attempts=max_attempts,
        egress_check=egress_check,
        on_retry=on_retry,
    )
    return response.json().get("results", {}).get("bindings", [])


async def get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    egress_check: Callable[[str], None] | None = None,
    on_retry: Callable[[int, str, Exception], None] | None = None,
) -> Any:
    """GET-JSON mit derselben Retry-Semantik wie `get_bindings`."""
    response = await _request_with_retry(
        client,
        "GET",
        url,
        params=params,
        headers=headers,
        base_delay=base_delay,
        max_attempts=max_attempts,
        egress_check=egress_check,
        on_retry=on_retry,
    )
    return response.json()
