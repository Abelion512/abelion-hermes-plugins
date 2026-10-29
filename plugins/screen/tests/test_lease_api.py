"""Lease lifecycle regression tests against the pinned gateway semantics.

Covers the two bugs fixed in v0.2/v0.3:
- a dashboard restart orphans the human lease on a dead viewer id; a plain
  Hand back must NOT silently release it (could be another LIVE viewer)
- force escalation only via an explicit force:true from the UI
Plus the happy path and the multiviewer/foreign-holder matrix.
"""
import hashlib
import json
import httpx
import pytest
from types import SimpleNamespace


def _observe(srv):
    r = httpx.post(f"{srv.base_http}/api/plugins/screen/observe", timeout=10)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] and j["viewer_id"]
    return j


def _lease(srv, action, body=None):
    return httpx.post(f"{srv.base_http}/api/plugins/screen/lease/{action}",
                      json=body, timeout=10)


def test_build_endpoint(plugin):
    r = httpx.get(f"{plugin.base_http}/api/plugins/screen/build", timeout=10)
    assert r.status_code == 200
    assert r.json()["build"].startswith("screen-plugin ")


def test_lease_requires_observe_first(plugin):
    r = _lease(plugin, "acquire")
    assert r.status_code == 409


def test_unknown_lease_action_404(plugin):
    _observe(plugin)
    r = _lease(plugin, "bogus")
    assert r.status_code == 404


def test_happy_path_acquire_release_no_force(plugin, upstream):
    _observe(plugin)
    j = _lease(plugin, "acquire").json()
    assert j["holder"] == "human" and j["we_hold"] is True
    j = _lease(plugin, "release").json()
    assert j["holder"] == "agent" and j["we_hold"] is False
    assert j["forced"] is False and j["recovery_required"] is False
    assert upstream.holder == "agent"


def test_restart_orphan_plain_release_does_not_escalate(plugin, upstream):
    """His actual bug: SIGINT/SIGKILL the dashboard while a human holds the
    lease. The lease survives on a viewer id the NEW connection never minted.
    A plain Hand back must report recovery_required WITHOUT releasing it."""
    _observe(plugin)
    assert _lease(plugin, "acquire").json()["we_hold"] is True
    plugin.restart()                      # abrupt dashboard death
    plugin.start()                        # new process, new upstream conn
    j = _observe(plugin)
    assert j["lease"]["holder"] == "human" and j["we_hold"] is False
    j = _lease(plugin, "release").json()  # generic Hand back
    assert j["holder"] == "human", "plain release must not drop a foreign lease"
    assert j["recovery_required"] is True
    assert j["forced"] is False
    assert upstream.holder == "human"         # still held upstream
    # explicit effect-naming UI action (force:true) recovers it
    j = _lease(plugin, "release", {"force": True}).json()
    assert j["holder"] == "agent" and j["forced"] is True
    assert upstream.holder == "agent"


def test_takeover_reclaims_orphaned_lease(plugin, upstream):
    """Take over after a restart: re-observe mints a fresh id and acquire is
    last-writer-wins, so control is recoverable without force."""
    _observe(plugin)
    _lease(plugin, "acquire")
    plugin.restart()
    plugin.start()
    _observe(plugin)
    j = _lease(plugin, "acquire").json()
    assert j["holder"] == "human" and j["we_hold"] is True
    assert hashlib.sha256(upstream.holder_id.encode()).hexdigest()[:12] == j["lease"]["viewer_hash"]
    assert upstream.holder_id not in json.dumps(j)
    assert upstream.holder == "human"


def test_foreign_live_holder_not_released_by_plain_hand_back(plugin, upstream):
    """Another LIVE viewer (phone, second dashboard) holds the lease:
    indistinguishable from an orphan, so plain release must not touch it."""
    _observe(plugin)
    # a foreign viewer acquires directly on the gateway
    import asyncio, aiohttp, json as _json

    async def foreign_acquire():
        async with aiohttp.ClientSession() as s:
            async with s.ws_connect(f"{upstream.base_ws}/api/ws?token=e2e-test-session-token") as ws:
                async def rpc(rid, method, params):
                    await ws.send_str(_json.dumps(
                        {"jsonrpc": "2.0", "id": rid, "method": method, "params": params}))
                    while True:
                        m = await ws.receive()
                        if m.type == aiohttp.WSMsgType.TEXT:
                            f = _json.loads(m.data)
                            if f.get("id") == rid:
                                return f.get("result")
                obs = await rpc(1, "display.observe", {})
                await rpc(2, "display.lease.acquire", {"viewer_id": obs["viewer_id"]})
                # keep the connection open briefly so the holder is LIVE
                await asyncio.sleep(0.1)
                await ws.close()

    asyncio.run(foreign_acquire())
    assert upstream.holder == "human"
    j = _lease(plugin, "release").json()
    assert j["holder"] == "human" and j["recovery_required"] is True
    assert upstream.holder == "human"


def test_force_survives_reconnect_retry(plugin, upstream):
    """Regression: force hand-back raced with an upstream reconnect must not
    degrade to a bare release (refused while a human holds). The first call
    hits 5300; the retry after re-observe must still carry force:true."""
    _observe(plugin)
    assert _lease(plugin, "acquire").json()["we_hold"] is True
    upstream.fail_next_release_not_minted = True
    j = _lease(plugin, "release", {"force": True}).json()
    assert j["holder"] == "agent", j
    assert j["forced"] is True
    assert upstream.holder == "agent"


def test_viewer_identity_stable_across_reload(plugin):
    """Reload must reuse the id minted by THIS connection so a held lease
    survives a tab reload (we_hold stays true)."""
    j1 = _observe(plugin)
    _lease(plugin, "acquire")
    j2 = _observe(plugin)  # reload
    assert j2["viewer_id"] == j1["viewer_id"]
    assert j2["we_hold"] is True


def _request_for_port(port=9119):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(bound_port=port)))


def test_upstream_override_is_ignored_outside_explicit_test_mode(monkeypatch):
    import plugin_api
    monkeypatch.setenv("HERMES_SCREEN_UPSTREAM", "ws://127.0.0.1:12345")
    monkeypatch.delenv("HERMES_SCREEN_TEST_MODE", raising=False)
    assert plugin_api._upstream_base(_request_for_port()) == "ws://127.0.0.1:9119"


def test_test_upstream_override_rejects_non_loopback_target(monkeypatch):
    import plugin_api
    monkeypatch.setenv("HERMES_SCREEN_TEST_MODE", "1")
    monkeypatch.setenv("HERMES_SCREEN_UPSTREAM", "ws://203.0.113.10:12345")
    with pytest.raises(plugin_api.UpstreamError):
        plugin_api._upstream_base(_request_for_port())


def test_missing_canonical_websocket_auth_denies_upgrade(monkeypatch):
    import hermes_cli.web_server_chat as chat
    import plugin_api
    monkeypatch.delattr(chat, "_ws_auth_ok")
    assert plugin_api._ws_upgrade_authorized(object()) is False


def test_canonical_websocket_auth_exception_denies_upgrade(monkeypatch):
    import hermes_cli.web_server_chat as chat
    import plugin_api
    def broken(_ws):
        raise RuntimeError("test-only auth failure")
    monkeypatch.setattr(chat, "_ws_auth_ok", broken)
    assert plugin_api._ws_upgrade_authorized(object()) is False
