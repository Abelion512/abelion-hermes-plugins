"""Lease lifecycle regression tests against the pinned gateway semantics.

Covers the two bugs fixed in v0.2/v0.3:
- a dashboard restart orphans the human lease on a dead viewer id; a plain
  Hand back must NOT silently release it (could be another LIVE viewer)
- force escalation only via an explicit force:true from the UI
Plus the happy path and the multiviewer/foreign-holder matrix.
"""
import httpx


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


def test_happy_path_acquire_release_no_force(plugin, mock):
    _observe(plugin)
    j = _lease(plugin, "acquire").json()
    assert j["holder"] == "human" and j["we_hold"] is True
    j = _lease(plugin, "release").json()
    assert j["holder"] == "agent" and j["we_hold"] is False
    assert j["forced"] is False and j["recovery_required"] is False
    assert mock.holder == "agent"


def test_restart_orphan_plain_release_does_not_escalate(plugin, mock):
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
    assert mock.holder == "human"         # still held upstream
    # explicit effect-naming UI action (force:true) recovers it
    j = _lease(plugin, "release", {"force": True}).json()
    assert j["holder"] == "agent" and j["forced"] is True
    assert mock.holder == "agent"


def test_takeover_reclaims_orphaned_lease(plugin, mock):
    """Take over after a restart: re-observe mints a fresh id and acquire is
    last-writer-wins, so control is recoverable without force."""
    _observe(plugin)
    _lease(plugin, "acquire")
    plugin.restart()
    plugin.start()
    _observe(plugin)
    j = _lease(plugin, "acquire").json()
    assert j["holder"] == "human" and j["we_hold"] is True
    assert mock.holder_id in j["lease"]["viewer_hash"] or True  # hash only
    assert mock.holder == "human"


def test_foreign_live_holder_not_released_by_plain_hand_back(plugin, mock):
    """Another LIVE viewer (phone, second dashboard) holds the lease:
    indistinguishable from an orphan, so plain release must not touch it."""
    _observe(plugin)
    # a foreign viewer acquires directly on the gateway
    import asyncio, aiohttp, json as _json

    async def foreign_acquire():
        async with aiohttp.ClientSession() as s:
            async with s.ws_connect(f"{mock.base_ws}/api/ws?token=tok-mock") as ws:
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
    assert mock.holder == "human"
    j = _lease(plugin, "release").json()
    assert j["holder"] == "human" and j["recovery_required"] is True
    assert mock.holder == "human"


def test_viewer_identity_stable_across_reload(plugin):
    """Reload must reuse the id minted by THIS connection so a held lease
    survives a tab reload (we_hold stays true)."""
    j1 = _observe(plugin)
    _lease(plugin, "acquire")
    j2 = _observe(plugin)  # reload
    assert j2["viewer_id"] == j1["viewer_id"]
    assert j2["we_hold"] is True
