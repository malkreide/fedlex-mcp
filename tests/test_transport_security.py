"""Eingehende Host/Origin-Prüfung des Streamable-HTTP-Transports (SEC-005).

Auslöser war kein fehlender Schutz, sondern ein zu strenger an der falschen
Adresse. mcp 2.x aktiviert automatisch eine Allow-List auf ``127.0.0.1:*``, wenn
das ``host``-Argument der App loopback-artig aussieht — und
``streamable_http_app()`` defaultet genau darauf. Jeder Start mit
``FEDLEX_HOST=0.0.0.0`` bekam damit auf jede Anfrage unter einem echten
Hostnamen HTTP 421.

Die Form des Fehlers ist hier besonders sichtbar: ``_run_http()`` baute die App
*bevor* Host und Port überhaupt aufgelöst waren. Der Bind konnte also gar nicht
ankommen. Er wird jetzt zuerst ermittelt (``resolve_http_bind``) und dann an
beide Abnehmer gegeben — uvicorn und die App.
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from fedlex_mcp.server import (
    build_http_app,
    build_transport_security,
    resolve_http_bind,
    settings,
)

_INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1"},
    },
}
_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setattr(settings, "allowed_hosts", "", raising=False)
    monkeypatch.setattr(
        settings, "allowed_origins", "http://localhost,http://127.0.0.1", raising=False
    )
    monkeypatch.delenv("FEDLEX_HOST", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    yield


def test_loopback_bind_is_protected():
    sec = build_transport_security("127.0.0.1", 8000)
    assert sec is not None
    assert sec.enable_dns_rebinding_protection is True
    assert "127.0.0.1:8000" in sec.allowed_hosts


def test_wildcard_bind_without_allowlist_stays_off():
    """Der eigentliche Fix.

    Auf 0.0.0.0 ist der erreichbare Name hier unbekannt, und der
    SDK-Loopback-Default ist genau eine Vermutung — er reproduziert das 421.
    """
    assert build_transport_security("0.0.0.0", 8000) is None


def test_wildcard_bind_with_allowlist_is_protected(monkeypatch):
    monkeypatch.setattr(settings, "allowed_hosts", "fedlex.example.ch")
    sec = build_transport_security("0.0.0.0", 8000)
    assert sec is not None
    assert "fedlex.example.ch" in sec.allowed_hosts
    # Loopback bleibt drin, sonst brechen Container-Health-Checks.
    assert "127.0.0.1:8000" in sec.allowed_hosts


def test_cors_origins_pass_the_transport_check(monkeypatch):
    """Sonst weist der Transport genau die Browser-Clients ab, die CORS erlaubt."""
    monkeypatch.setattr(settings, "allowed_origins", "https://claude.ai")
    sec = build_transport_security("127.0.0.1", 8000)
    assert "https://claude.ai" in sec.allowed_origins


def test_wildcard_cors_is_not_copied(monkeypatch):
    monkeypatch.setattr(settings, "allowed_origins", "*")
    sec = build_transport_security("127.0.0.1", 8000)
    assert "*" not in sec.allowed_origins


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
def test_all_loopback_forms_count_as_local(host):
    assert build_transport_security(host, 8000) is not None


def _post(app, host_header: str) -> int:
    with TestClient(app) as client:
        return client.post(
            "/mcp", headers={"Host": host_header, **_HEADERS}, json=_INIT
        ).status_code


def test_a_public_bind_is_reachable_again():
    """Die Regression selbst, durch den echten ASGI-Stack.

    Ohne den ``host``-Kwarg ist das ein 421 — der Zustand, den dieser Commit
    behebt.
    """
    assert _post(build_http_app("0.0.0.0", 8000), "fedlex.example.ch") == 200


def test_configured_host_is_served(monkeypatch):
    monkeypatch.setattr(settings, "allowed_hosts", "fedlex.example.ch")
    assert _post(build_http_app("0.0.0.0", 8000), "fedlex.example.ch") == 200


def test_foreign_host_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "allowed_hosts", "fedlex.example.ch")
    assert _post(build_http_app("0.0.0.0", 8000), "evil.example.com") == 421


def test_right_host_wrong_port_is_rejected(monkeypatch):
    """Der tragende Fall.

    ``evil.example.com`` allein beweist wenig: ein zurückfallender
    Loopback-Default würde ihn ebenfalls abweisen. Nur „richtiger Hostname,
    falscher Port" unterscheidet eine portgenaue Allow-List von einer, die alles
    durchlässt.
    """
    monkeypatch.setattr(settings, "allowed_hosts", "fedlex.example.ch:8000")
    assert _post(build_http_app("0.0.0.0", 8000), "fedlex.example.ch:9999") == 421


def test_bind_resolution_order(monkeypatch):
    """PORT der Cloud-Plattform schlägt --port, --port schlägt die Settings.

    Der Bind muss vor dem App-Bau feststehen; diese Reihenfolge festzunageln
    verhindert, dass die App später wieder einen anderen Wert sieht als uvicorn.
    """
    monkeypatch.setenv("FEDLEX_HOST", "0.0.0.0")
    assert resolve_http_bind(["prog", "--port", "9001"]) == ("0.0.0.0", 9001)
    monkeypatch.setenv("PORT", "9999")
    assert resolve_http_bind(["prog", "--port", "9001"]) == ("0.0.0.0", 9999)
