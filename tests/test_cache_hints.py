"""SEP-2549: die auflistenden Methoden muessen einen Frischehinweis tragen.

Spec `2026-07-28` gibt jedem cachebaren Resultat `ttlMs` und `cacheScope`. Das
SDK fuellt von sich aus keines von beiden — `CacheHint()` defaultet auf
`ttl_ms=0`, `scope="private"`, die Drahtform von «schon veraltet, nie teilen».
Ein Server ohne `cache_hints` verhaelt sich also nicht neutral: er laesst jeden
Client bei jeder Verbindung neu auflisten, fuer Listen, die beim Import
feststehen.

Geprueft ueber eine echte `ClientSession`, nicht durch Ruecklesen von
`CACHE_HINTS`. `MCPServer` fuellt den Hinweis feldweise und nur dort, wo der
Handler nichts gesetzt hat — ein Blick ins Dict waere auch dann gruen, wenn das
Argument am Konstruktor verlorenginge.
"""

from __future__ import annotations

from mcp import Client
from mcp.server.caching import CACHEABLE_METHODS
from mcp.server.mcpserver import MCPServer

from fedlex_mcp.server import CACHE_HINTS, LIST_CACHE_TTL_MS, mcp


async def test_die_werkzeugliste_traegt_die_ttl() -> None:
    async with Client(mcp) as client:
        result = await client.list_tools()

    assert result.ttl_ms == LIST_CACHE_TTL_MS, (
        f"tools/list antwortete mit ttlMs={result.ttl_ms}; bei 0 listet jeder Client "
        "bei jeder Verbindung neu auf"
    )
    assert result.cache_scope == "public"


async def test_die_ressourcenliste_traegt_die_ttl() -> None:
    """Die beiden Ressourcen werden per Dekorator beim Import registriert, die
    Liste haengt also so wenig vom Aufrufer ab wie die der Tools."""
    async with Client(mcp) as client:
        result = await client.list_resources()

    assert result.ttl_ms == LIST_CACHE_TTL_MS
    assert result.cache_scope == "public"


async def test_der_inhalt_einer_ressource_traegt_keinen_frischehinweis() -> None:
    """Die wichtigste Zusicherung hier, und die einzige negative.

    `resources/read` liefert geltendes Bundesrecht. Ein Client, der eine solche
    Antwort fuenf Minuten als frisch behandelt, zeigt unter Umstaenden einen
    aufgehobenen Erlass — die Liste sagt, WELCHE Ressourcen es gibt, und nur
    das ist die statische Angabe. Faellt dieser Test, hat jemand
    `resources/read` in `CACHE_HINTS` aufgenommen.
    """
    async with Client(mcp) as client:
        result = await client.read_resource("fedlex://info")

    assert result.ttl_ms == 0, "der Inhalt einer Ressource darf keine Haltbarkeit versprechen"
    assert result.cache_scope == "private"


async def test_ein_server_ohne_hinweise_sagt_nichts() -> None:
    """Negativkontrolle: gleiches SDK, gleicher Client, kein `cache_hints`.

    Faengt den Tag ab, an dem das SDK selbst einen Default bekommt — dann
    pruefen die Tests oben naemlich nicht mehr, dass wir ihn setzen.
    """
    async with Client(MCPServer("kontrolle")) as client:
        result = await client.list_tools()

    assert result.ttl_ms == 0
    assert result.cache_scope == "private"


def test_jede_gehinweiste_methode_ist_nach_spec_cachebar() -> None:
    """`MCPServer` lehnt einen unbekannten Schluessel schon im Konstruktor ab —
    ein Tippfehler waere also ein Import-Fehler und taeuchte als Collection-Error
    an ganz anderer Stelle auf. Hier steht er benannt."""
    unknown = sorted(set(CACHE_HINTS) - set(CACHEABLE_METHODS))
    assert not unknown, f"nach Spec 2026-07-28 nicht cachebar: {unknown}"


def test_resources_read_steht_nicht_in_den_hinweisen() -> None:
    """Dieselbe Zusicherung wie oben, aber an der Konfiguration statt an der
    Antwort — damit die Absicht auch dann sichtbar bleibt, wenn jemand die
    Ressource `fedlex://info` einmal entfernt."""
    assert "resources/read" not in CACHE_HINTS
