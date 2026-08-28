"""Was passiert, wenn der Endpoint antwortet — aber nicht mit JSON?

HERKUNFT
--------
Portfolio-Nachzug aus `swiss-environment-mcp`. Dort fielen am 23.8.2026 in der
nächtlichen Live-Suite zwei Tests, weil `opendata.swiss` mit HTTP 2xx und einem
Body antwortete, der kein JSON war. Der `json.JSONDecodeError` fiel in den
Sammelzweig der Fehlerabbildung und kam als «Unerwarteter Fehler» heraus — eine
Meldung, die auf den Server zeigt, obwohl die Quelle den Vertrag gebrochen
hatte, und die weder Status noch Content-Type nennt.

Hier steckt dieselbe Stelle in der vendored copy `sparql_client.py`, und zwar in
`get_bindings` — dem Pfad, den dieser Server für **jede** SPARQL-Abfrage fährt.
Ein Endpoint, der eine HTML-Wartungsseite mit 200 ausliefert, hätte jedes Tool
mit «Unerwarteter Fehler beim Abruf vom Fedlex-Endpoint» beantwortet.

`get_json` ist in diesem Server unbenutzt und wird trotzdem mitgeprüft: Die
Datei ist eine byte-identische Kopie, und die Kopie hier ist genau die, die als
Nächstes irgendwo benutzt wird.

GEGENPROBE
----------
Jede Zusicherung ist einzeln neutralisierbar; die Messung steht im PR. Kurz:
`_json_body`-Rumpf auf nacktes `.json()` zurückdrehen → die Parser-Tests fallen;
den `NotJsonError`-Zweig in `handle_error` entfernen → die Meldungs-Tests fallen;
den `isinstance(payload, dict)`-Guard entfernen → `test_gueltiges_json_in_der
_falschen_form` fällt.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from fedlex_mcp import sparql_client as c
from fedlex_mcp.server import handle_error

URL = "https://fedlex.data.admin.ch/sparqlendpoint"

# Die HTML-Fehlerseite, wie ein Reverse-Proxy sie mit einem 200 ausliefert.
_HTML = "<html><head><title>503 Service Unavailable</title></head><body>...</body></html>"


def _resp(status: int = 200, text: str = _HTML, content_type: str = "text/html"):
    return httpx.Response(
        status,
        text=text,
        headers={"content-type": content_type},
        request=httpx.Request("GET", URL),
    )


# --- Der Parser benennt den gebrochenen Vertrag -------------------------------


def test_json_body_wirft_notjsonerror_statt_valueerror():
    with pytest.raises(c.NotJsonError) as exc:
        c._json_body(_resp())

    assert exc.value.status_code == 200
    assert exc.value.content_type == "text/html"
    # Der Auszug trennt eine HTML-Fehlerseite von einem leeren Body — genau die
    # Frage, die im Ursprungsfall offenblieb.
    assert "503 Service Unavailable" in exc.value.excerpt


def test_json_body_erkennt_auch_den_leeren_body():
    """«Expecting value: line 1 column 1» kommt auch von einer Antwort ohne Inhalt."""
    with pytest.raises(c.NotJsonError) as exc:
        c._json_body(_resp(text="", content_type=""))

    assert exc.value.excerpt == ""
    assert exc.value.content_type == ""


def test_json_body_laesst_gueltiges_json_durch():
    """Die Gegenrichtung: der Guard darf den Normalfall nicht abwürgen."""
    ok = httpx.Response(200, json={"a": 1}, request=httpx.Request("GET", URL))
    assert c._json_body(ok) == {"a": 1}


# --- Der Pfad, den dieser Server tatsächlich fährt ----------------------------


@respx.mock
async def test_get_bindings_auf_html_antwort():
    respx.get(URL).mock(return_value=_resp())
    async with httpx.AsyncClient() as http:
        with pytest.raises(c.NotJsonError):
            await c.get_bindings(http, URL, "SELECT * WHERE {?s ?p ?o} LIMIT 1")


@respx.mock
async def test_gueltiges_json_in_der_falschen_form():
    """Gültiges JSON ist noch nicht die vereinbarte Form.

    Eine Liste statt des SPARQL-Umschlags warf vorher `AttributeError: 'list'
    object has no attribute 'get'` — wieder ein Typ, den `handle_error` nicht
    kennt, wieder «Unerwarteter Fehler» für einen Vertragsbruch der Quelle.
    """
    respx.get(URL).mock(return_value=httpx.Response(200, json=[1, 2, 3]))
    async with httpx.AsyncClient() as http:
        with pytest.raises(c.NotJsonError):
            await c.get_bindings(http, URL, "SELECT * WHERE {?s ?p ?o} LIMIT 1")


@respx.mock
async def test_get_bindings_liefert_bindings_im_normalfall():
    """Gegenprobe zu den beiden darüber: der gültige Umschlag muss durchkommen."""
    envelope = {"results": {"bindings": [{"s": {"value": "urn:x"}}]}}
    respx.get(URL).mock(return_value=httpx.Response(200, json=envelope))
    async with httpx.AsyncClient() as http:
        got = await c.get_bindings(http, URL, "SELECT * WHERE {?s ?p ?o} LIMIT 1")
    assert got == [{"s": {"value": "urn:x"}}]


@respx.mock
async def test_get_json_auf_html_antwort():
    """Von diesem Server unbenutzt, aber Teil der byte-identischen Kopie."""
    respx.get(URL).mock(return_value=_resp())
    async with httpx.AsyncClient() as http:
        with pytest.raises(c.NotJsonError):
            await c.get_json(http, URL)


# --- Die Meldung zeigt auf den Endpoint, nicht auf uns ------------------------


def test_handle_error_benennt_den_endpoint():
    msg = handle_error("x", c.NotJsonError(URL, 200, "text/html", "<html>"))

    assert "HTTP 200" in msg
    assert "text/html" in msg
    assert "Endpoints" in msg
    # Der Kern: nicht mehr die Meldung, die auf uns zeigt.
    assert "Unerwarteter Fehler" not in msg


def test_handle_error_nennt_den_betroffenen_dienst():
    """`service` trägt auch im neuen Zweig — sonst schliesst das Modell bei
    einem isolierten LINDAS-Ausfall auf einen Fedlex-Fehler.

    Die Zusicherung auf «kein JSON» steht hier, weil der Test sonst nichts
    unterscheidet: Der generische Sammelzweig nennt `service` ebenfalls, also
    bliebe er auch ohne den neuen Zweig grün. Gemessen — genau das tat er.
    """
    msg = handle_error("x", c.NotJsonError(URL, 200, "text/html", ""), service="TERMDAT (LINDAS)")
    assert "TERMDAT (LINDAS)" in msg
    assert "Fedlex" not in msg
    assert "kein JSON" in msg


def test_handle_error_leakt_keine_interna():
    """OBS-002: Body-Auszug und URL gehören ins Log, nicht in die Meldung."""
    msg = handle_error("x", c.NotJsonError(URL, 200, "text/html", "<html>geheim-xyz</html>"))
    assert "geheim-xyz" not in msg
    assert URL not in msg


def test_gegenprobe_nacktes_json_faellt_in_den_sammelzweig():
    """Ohne den neuen Typ kommt exakt die alte, nichtssagende Meldung heraus."""
    try:
        _resp().json()
    except ValueError as e:
        assert handle_error("x", e) == (
            "Fehler: Unerwarteter Fehler beim Abruf vom Fedlex-Endpoint. Bitte erneut versuchen."
        )
    else:  # pragma: no cover - json() muss auf HTML scheitern
        pytest.fail("HTML-Body wurde als JSON geparst")
