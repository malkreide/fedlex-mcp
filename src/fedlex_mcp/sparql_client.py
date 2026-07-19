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
from collections.abc import Callable
from typing import Any

import httpx

# Transiente HTTP-Status → Retry. 4xx (ausser 429) sind deterministisch.
RETRYABLE_STATUS: frozenset[int] = frozenset({429, 502, 503, 504})
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BASE_DELAY = 0.5  # Sekunden; exp. Backoff base*2**attempt. Tests: 0.


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
) -> httpx.Response:
    """Gemeinsamer Retry-Kern für GET-Requests (SPARQL + JSON)."""
    if egress_check is not None:
        egress_check(url)
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            response = await client.request(method, url, params=params, headers=headers)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            if e.response.status_code not in RETRYABLE_STATUS:
                raise
            last_exc = e
        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as e:
            last_exc = e
        if attempt < max_attempts - 1:
            if on_retry is not None:
                on_retry(attempt + 1, url, last_exc)
            await asyncio.sleep(base_delay * (2**attempt))
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
