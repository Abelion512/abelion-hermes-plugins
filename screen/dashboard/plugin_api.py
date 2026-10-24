"""Screen dashboard plugin — backend API, mounted at /api/plugins/screen/.

Live Bot Screen in a dashboard tab: display.observe/status/lease.* over ONE
persistent authenticated WS client to this dashboard's own /api/ws, plus a
ticket-gated RFB splice so the tab's noVNC session never sees the one-time
display ticket.

Transport & identity (pinned contract, hermes v0.22.5 bf0203a):
- viewer ids are minted PER upstream WS connection (tui_gateway/
  methods_display.py:112-145); lease.* rejects ids the live connection never
  minted. So this module keeps one persistent connection, tracks which ids it
  minted, and re-observes before lease calls after any reconnect. We never
  touch the process-wide minted-id fallback (that path is for transports that
  cannot be weakref'd, e.g. the TUI's stdio pipe - using it from a shared
  dashboard process would weaken per-connection capability isolation).
- Auth uses official routes only, no scraping: loopback mode presents the
  in-process session token (web_server._SESSION_TOKEN, the same credential
  injected into the SPA as __HERMES_SESSION_TOKEN__); gated mode presents the
  internal server-spawned credential (dashboard_auth.ws_tickets.
  internal_ws_credential - the documented seam for server-side WS clients).
- The browser-facing WS is gated by the dashboard's canonical check
  (web_server_chat._ws_auth_ok), so plugin auth can never drift from core.
- Lease lifecycle is Hermes's own (web_routers/display.py): a CLEAN viewer
  close auto-hands control back to the agent; an ABRUPT drop keeps the human
  lease. The splice mirrors the browser's close nature upstream so that
  protection survives.

HERMES_SCREEN_UPSTREAM (test-only): point RPC + RFB at another ws base
(e.g. the synthetic mock) instead of this dashboard's own loopback.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os

import aiohttp
from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

log = logging.getLogger(__name__)

router = APIRouter()

BUILD = "screen-plugin v0.2-20261024"
MAX_WS_FRAME = 64 * 1024 * 1024
ALLOWED_RPC = ("display.observe", "display.status",
               "display.lease.acquire", "display.lease.release")


# --- upstream RPC client -----------------------------------------------------

class UpstreamError(Exception):
    def __init__(self, code, message, hint=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint


def _upstream_base(request: Request) -> str:
    override = os.environ.get("HERMES_SCREEN_UPSTREAM", "").strip()
    if override:
        return override.rstrip("/")
    port = getattr(request.app.state, "bound_port", None) or 9119
    return f"ws://127.0.0.1:{port}"


async def _upstream_credential(base_ws: str) -> str:
    """Query-string credential for OUR server-spawned client connection."""
    if os.environ.get("HERMES_SCREEN_UPSTREAM", "").strip():
        # Test harness: the mock injects the same bootstrap token in its /.
        return "token", await _scrape_session_token("http" + base_ws[2:])
    from hermes_cli.web_server import app
    if getattr(app.state, "auth_required", False):
        # Gated mode: _SESSION_TOKEN is deliberately refused; the official
        # route for server-spawned WS clients is the internal credential.
        from hermes_cli.dashboard_auth.ws_tickets import internal_ws_credential
        return "internal", internal_ws_credential()
    from hermes_cli.web_server import _SESSION_TOKEN
    return "token", _SESSION_TOKEN


async def _scrape_session_token(http_base: str, timeout: float = 10.0) -> str:
    import re
    async with aiohttp.ClientSession() as sess:
        async with sess.get(http_base + "/", timeout=timeout) as r:
            html = await r.text()
    m = re.search(r'__HERMES_SESSION_TOKEN__\s*=\s*"([^"]+)"', html)
    if not m:
        raise UpstreamError(None, "session token not found on upstream /")
    return m.group(1)


class GatewayRpc:
    """One persistent WS per dashboard run; calls serialized, matched by id.
    Tracks which viewer ids the LIVE connection minted (cleared on reconnect)."""

    def __init__(self, base_ws: str, timeout: float = 15.0):
        self.base_ws = base_ws
        self.timeout = timeout
        self._session = None
        self._ws = None
        self._lock = asyncio.Lock()
        self._next_id = 0
        self.minted_ids: set = set()

    def _connected(self) -> bool:
        return self._ws is not None and not self._ws.closed

    async def _connect(self) -> None:
        await self._drop()
        kind, cred = await _upstream_credential(self.base_ws)
        url = f"{self.base_ws}/api/ws?{kind}={cred}"
        self._session = aiohttp.ClientSession()
        try:
            self._ws = await self._session.ws_connect(url, timeout=self.timeout)
        except (aiohttp.ClientConnectorError, ConnectionError, OSError):
            await self._drop()
            raise UpstreamError(
                None, "backend Hermes tidak bisa dihubungi di " + self.base_ws,
                hint="pastikan hermes dashboard jalan")
        except aiohttp.WSServerHandshakeError as e:
            await self._drop()
            raise UpstreamError(e.status, f"gateway menolak koneksi (HTTP {e.status})")
        self.minted_ids = set()  # new transport -> nothing minted here yet

    async def _drop(self) -> None:
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
        self._ws = None
        if self._session is not None:
            try:
                await self._session.close()
            except Exception:
                pass
        self._session = None
        self.minted_ids = set()

    async def call(self, method: str, params: dict | None = None) -> dict:
        async with self._lock:
            if not self._connected():
                await self._connect()
            try:
                result = await self._roundtrip(method, params or {})
            except UpstreamError as e:
                if e.code is not None:
                    raise  # a real RPC-level answer, not a transport problem
                await self._connect()  # transport broke: heal once and retry
                result = await self._roundtrip(method, params or {})
            if method == "display.observe":
                vid = result.get("viewer_id")
                if vid:
                    self.minted_ids.add(vid)
            return result

    async def _roundtrip(self, method: str, p: dict) -> dict:
        ws = self._ws
        self._next_id += 1
        rpc_id = self._next_id
        try:
            await ws.send_str(json.dumps(
                {"jsonrpc": "2.0", "id": rpc_id, "method": method, "params": p},
                ensure_ascii=False))
        except (ConnectionError, aiohttp.ClientError, OSError) as e:
            raise UpstreamError(None, f"koneksi upstream putus sebelum {method}: {e}")
        loop = asyncio.get_event_loop()
        deadline = loop.time() + self.timeout
        while True:
            left = deadline - loop.time()
            if left <= 0:
                raise UpstreamError(None, f"timeout waiting for {method}")
            try:
                msg = await ws.receive(timeout=left)
            except asyncio.TimeoutError:
                raise UpstreamError(None, f"timeout waiting for {method}")
            except (ConnectionError, aiohttp.ClientError, OSError) as e:
                raise UpstreamError(None, f"koneksi upstream putus saat {method}: {e}")
            if msg.type != aiohttp.WSMsgType.TEXT:
                if msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR,
                                aiohttp.WSMsgType.CLOSE):
                    raise UpstreamError(
                        None, f"upstream WS closed during {method} (code {ws.close_code})")
                continue
            try:
                frame = json.loads(msg.data)
            except ValueError:
                continue
            if frame.get("method") or "id" not in frame:
                continue  # server->client notification (gateway.ready, events)
            if frame.get("id") != rpc_id:
                continue
            if "error" in frame:
                err = frame["error"] or {}
                raise UpstreamError(err.get("code"),
                                    err.get("message", f"{method} failed"))
            return frame.get("result") or {}


# --- plugin state ------------------------------------------------------------

_rpc: GatewayRpc | None = None
_rpc_base: str | None = None
_ticket: str | None = None
_viewer_id: str | None = None


def _we_hold(lease: dict | None) -> bool:
    """True when the human lease is held by OUR live viewer id. Hermes never
    publishes the raw holder id (it is a capability); public_view replaces it
    with sha256(id)[:12] (tools/bot_desktop/lease.py public_view), so the
    holder can recognise itself - and a restart-orphaned lease (holder id
    minted by a dead connection) is distinguishable from one we hold."""
    if not lease or lease.get("holder") != "human" or not _viewer_id:
        return False
    return lease.get("viewer_hash") == hashlib.sha256(
        _viewer_id.encode()).hexdigest()[:12]


def _client(request: Request) -> GatewayRpc:
    global _rpc, _rpc_base
    base = _upstream_base(request)
    if _rpc is None or _rpc_base != base:
        _rpc = GatewayRpc(base)
        _rpc_base = base
    return _rpc


def _err(e: UpstreamError) -> JSONResponse:
    status = 503 if e.code is None else 502
    body = {"ok": False, "error": e.message, "code": e.code}
    if e.hint:
        body["hint"] = e.hint
    return JSONResponse(body, status_code=status)


async def _rpc_call(request: Request, method: str, params: dict | None = None) -> dict:
    if method not in ALLOWED_RPC:
        raise UpstreamError(None, f"method not allowed: {method}")
    return await _client(request).call(method, params)


# --- HTTP routes --------------------------------------------------------------

@router.get("/build")
async def build():
    return {"ok": True, "build": BUILD}


@router.get("/status")
async def status(request: Request):
    try:
        result = await _rpc_call(request, "display.status")
    except UpstreamError as e:
        return _err(e)
    return {"ok": True, "status": result,
            "we_hold": _we_hold((result or {}).get("lease"))}


@router.post("/observe")
async def observe(request: Request):
    global _ticket, _viewer_id
    params = {}
    # Hermes honours a requested id minted by THIS connection: reusing it
    # keeps identity (and its lease) stable across tab reloads.
    if _viewer_id and _rpc is not None and _viewer_id in _rpc.minted_ids:
        params["viewer_id"] = _viewer_id
    try:
        result = await _rpc_call(request, "display.observe", params)
    except UpstreamError as e:
        return _err(e)
    _ticket = result.get("ticket")   # stays server-side; the tab never sees it
    _viewer_id = result.get("viewer_id")
    return {"ok": True, "viewer_id": _viewer_id,
            "geometry": result.get("geometry"),
            "running": result.get("running"),
            "lease": result.get("lease"),
            "we_hold": _we_hold(result.get("lease"))}


@router.post("/lease/{action}")
async def lease(request: Request, action: str):
    global _ticket, _viewer_id
    if action not in ("acquire", "release"):
        raise HTTPException(status_code=404, detail="unknown lease action")
    if not _viewer_id:
        return JSONResponse({"ok": False, "error": "observe first"}, status_code=409)
    # force:true is passed through ONLY when the browser asked for it
    # explicitly. A foreign-held human lease (viewer_hash != ours) can be a
    # dead id from before a restart OR another LIVE viewer (second tab,
    # Hermes Desktop, the phone) - the plugin cannot tell them apart, so a
    # generic Hand back must never escalate on its own.
    force = False
    if action == "release":
        try:
            body = await request.json()
        except Exception:
            body = None
        force = isinstance(body, dict) and body.get("force") is True
    # If the live connection never minted our id (reconnect), re-observe
    # first: that also refreshes ticket + identity.
    if _rpc is not None and _viewer_id not in _rpc.minted_ids:
        try:
            observed = await _rpc_call(request, "display.observe")
        except UpstreamError as e:
            return _err(e)
        _ticket = observed.get("ticket")
        _viewer_id = observed.get("viewer_id")
    params = {"viewer_id": _viewer_id}
    if force:
        params = {"force": True}
    try:
        result = await _rpc_call(request, f"display.lease.{action}", params)
    except UpstreamError as e:
        # The connection may have dropped after our pre-check; "not minted"
        # means the (new) transport never observed. Re-observe once, retry.
        if e.code == 5300 and "not minted" in e.message:
            try:
                observed = await _rpc_call(request, "display.observe")
                _ticket = observed.get("ticket")
                _viewer_id = observed.get("viewer_id")
                result = await _rpc_call(request, f"display.lease.{action}",
                                         {"viewer_id": _viewer_id})
            except UpstreamError as e2:
                return _err(e2)
        else:
            return _err(e)
    lease_view = result.get("lease") or {}
    return {"ok": result.get("ok", True),
            "holder": lease_view.get("holder"),
            "lease": result.get("lease"),
            "we_hold": _we_hold(lease_view),
            # True when a plain release changed nothing because a foreign id
            # holds the lease: the UI must offer the explicit recovery step.
            "recovery_required": (action == "release" and not force
                                  and lease_view.get("holder") == "human"
                                  and not _we_hold(lease_view)),
            "forced": force,
            "reason": result.get("reason")}


# --- RFB splice (ticket stays server-side) ------------------------------------

def _ws_upgrade_authorized(ws: WebSocket) -> bool:
    """Gate on the dashboard's canonical WS auth (web_server_chat._ws_auth_ok)
    so this endpoint can never drift from core auth."""
    try:
        from hermes_cli import web_server_chat as _ws
    except Exception:
        return True  # bare-FastAPI test harness
    return bool(_ws._ws_auth_ok(ws))


@router.websocket("/display/ws")
async def display_ws(ws: WebSocket):
    if not _ws_upgrade_authorized(ws):
        await ws.close(code=4401)
        return
    if not _ticket:
        await ws.close(code=4409)
        return
    await ws.accept()
    base = _rpc_base or "ws://127.0.0.1:9119"
    url = f"{base}/api/display/ws?display_ticket={_ticket}"
    sess = aiohttp.ClientSession()
    try:
        up = await sess.ws_connect(url, max_msg_size=MAX_WS_FRAME)
    except aiohttp.ClientResponseError:
        log.warning("upstream display bridge refused the ticket")
        await sess.close()
        await ws.close(code=4401)
        return
    except (aiohttp.ClientConnectorError, ConnectionError, OSError):
        log.warning("upstream display bridge unreachable")
        await sess.close()
        await ws.close(code=1011)
        return

    clean = False  # did the BROWSER close its websocket politely?

    async def down():  # browser -> upstream
        nonlocal clean
        while True:
            try:
                m = await ws.receive()
            except WebSocketDisconnect as d:
                clean = d.code in (1000, 1001)
                return
            if m["type"] == "websocket.disconnect":
                clean = (m.get("code") or 1005) in (1000, 1001)
                return
            if m.get("bytes") is not None:
                await up.send_bytes(m["bytes"])
            elif m.get("text") is not None:
                await up.send_str(m["text"])

    async def up_pump():  # upstream -> browser
        async for m in up:
            if m.type == aiohttp.WSMsgType.BINARY:
                await ws.send_bytes(m.data)
            elif m.type == aiohttp.WSMsgType.TEXT:
                await ws.send_text(m.data)
            else:
                return

    try:
        done, pending = await asyncio.wait(
            (asyncio.ensure_future(down()), asyncio.ensure_future(up_pump())),
            return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
    except Exception:
        log.exception("display splice failed")
    finally:
        # Mirror the browser's goodbye upstream so Hermes applies its own
        # lease semantics: CLEAN close -> auto hand-back to the agent;
        # ABRUPT drop -> human lease kept.
        if clean:
            try:
                await up.close()
            except Exception:
                pass
        await sess.close()
        try:
            await ws.close()
        except Exception:
            pass
