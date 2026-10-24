"""RFB splice tests: ticket gating, auth-gate delegation, echo passthrough,
and mirroring the browser's close nature upstream (clean -> hand-back,
abrupt -> keep)."""
import json, sys, types

import httpx
import websocket  # websocket-client


def _observe(srv):
    r = httpx.post(f"{srv.base_http}/api/plugins/screen/observe", timeout=10)
    assert r.status_code == 200, r.text


def _ws_url(srv):
    return f"ws://127.0.0.1:{srv.port}/api/plugins/screen/display/ws"


def test_ws_requires_observe_first(plugin):
    try:
        websocket.create_connection(_ws_url(plugin), timeout=5)
        raise AssertionError("expected close 4409 before observe")
    except websocket.WebSocketBadStatusException:
        pass  # some servers reject at handshake
    except websocket.WebSocketConnectionClosedException:
        pass


def test_ws_auth_gate_delegates_to_core_check(plugin, monkeypatch):
    """When hermes_cli.web_server_chat is importable, its _ws_auth_ok verdict
    must be honoured: False -> 4401 close, never a silent fallback."""
    fake_chat = types.ModuleType("hermes_cli.web_server_chat")
    fake_chat._ws_auth_ok = lambda ws: False
    fake_pkg = types.ModuleType("hermes_cli")
    fake_pkg.web_server_chat = fake_chat
    monkeypatch.setitem(sys.modules, "hermes_cli", fake_pkg)
    monkeypatch.setitem(sys.modules, "hermes_cli.web_server_chat", fake_chat)
    _observe(plugin)
    try:
        ws = websocket.create_connection(_ws_url(plugin), timeout=5)
        ws.recv()  # server should close immediately with 4401
        ws.recv()
        raise AssertionError("expected 4401 close")
    except websocket.WebSocketBadStatusException:
        pass  # handshake rejected (server closes before accept)
    except websocket.WebSocketConnectionClosedException:
        pass


def test_splice_echo_and_clean_close(plugin, mock):
    _observe(plugin)
    ws = websocket.create_connection(_ws_url(plugin), timeout=5)
    ws.send_binary(b"\x01\x02\x03")
    assert ws.recv() == b"\x01\x02\x03"
    ws.close()  # polite -> splice mirrors a CLEAN close upstream
    import time
    time.sleep(0.5)
    assert "clean" in mock.display_conns.values(), mock.display_conns
