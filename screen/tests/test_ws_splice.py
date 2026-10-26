"""RFB splice tests: ticket gating, auth-gate delegation, echo passthrough,
and mirroring the browser's close nature upstream (clean -> hand-back,
abrupt -> keep)."""
import json, struct, sys, types

import httpx
import websocket  # websocket-client


def _observe(srv):
    r = httpx.post(f"{srv.base_http}/api/plugins/screen/observe", timeout=10)
    assert r.status_code == 200, r.text


def _ws_url(srv):
    return f"ws://127.0.0.1:{srv.port}/api/plugins/screen/display/ws"


def test_ws_requires_observe_first(plugin):
    """No fresh /observe -> readable 4409 close after accept (v0.4 contract;
    v0.3 rejected at the handshake, indistinguishable from a network drop)."""
    ws = websocket.create_connection(_ws_url(plugin), timeout=5)
    code, _ = _close_code(ws)
    assert code == 4409, code


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


def test_ws_auth_fails_closed_without_core_module(plugin, monkeypatch):
    """Production boundary: if hermes_cli.web_server_chat cannot be imported
    (e.g. a Hermes update renames it), the display WS must be REFUSED - never
    fail open - even after a valid /observe."""
    _observe(plugin)
    monkeypatch.delitem(sys.modules, "hermes_cli", raising=False)
    monkeypatch.delitem(sys.modules, "hermes_cli.web_server_chat", raising=False)
    try:
        ws = websocket.create_connection(_ws_url(plugin), timeout=5)
        ws.recv()
        raise AssertionError("upgrade must be refused when core auth is missing")
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


def _close_code(ws):
    """Read the next frame and return (code, reason) of a CLOSE frame."""
    frame = ws.recv_frame()
    assert frame.opcode == websocket.ABNF.OPCODE_CLOSE, frame.opcode
    payload = frame.data
    code = struct.unpack("!H", payload[:2])[0] if len(payload) >= 2 else None
    return code, payload[2:].decode("utf-8", "replace")


def test_no_ticket_close_is_readable_4409(plugin):
    """Regression (v0.4): without a fresh /observe the ws must close AFTER
    accept with 4409 + reason. v0.3 closed pre-accept (bare 1006) or let a
    stale ticket through, so the tab only ever saw a black screen."""
    ws = websocket.create_connection(_ws_url(plugin), timeout=5)
    code, reason = _close_code(ws)
    assert code == 4409, code
    assert "observe" in reason


def test_ticket_is_single_use_per_observe(plugin, mock):
    """Regression (v0.4): a second ws without a fresh /observe must NOT ride
    the previous ticket (two tabs / rapid double refresh raced on it)."""
    _observe(plugin)
    ws1 = websocket.create_connection(_ws_url(plugin), timeout=5)
    ws1.send_binary(b"\x05")
    assert ws1.recv() == b"\x05"
    ws2 = websocket.create_connection(_ws_url(plugin), timeout=5)
    code, _ = _close_code(ws2)
    assert code == 4409, code
    ws1.close()


def test_upstream_close_code_forwarded_and_recorded(plugin, mock):
    """Regression (v0.4): an upstream refusal (e.g. 4401 ticket already
    consumed) must reach the tab as 4401 - v0.3 proxied every upstream
    failure as a bare 1000 - and /display/last_close must explain it."""
    mock.close_display_with = 4401
    try:
        _observe(plugin)
        ws = websocket.create_connection(_ws_url(plugin), timeout=5)
        code, reason = _close_code(ws)
        assert code == 4401, code
    finally:
        mock.close_display_with = None
    import httpx as _h, time as _t
    _t.sleep(0.3)
    j = _h.get(f"{plugin.base_http}/api/plugins/screen/display/last_close",
               timeout=10).json()
    lc = j["last_close"]
    assert lc["code"] == 4401 and lc["side"] == "upstream", lc
