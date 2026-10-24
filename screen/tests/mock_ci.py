"""In-process mock of the pinned Hermes display.* RPC contract (bf0203a),
plus an echo /api/display/ws that records how each connection ended.

RPC semantics mirrored from the real gateway (tui_gateway/methods_display.py,
tools/bot_desktop/lease.py):
- viewer ids are minted PER WS connection; a requested id is honoured only
  if THIS connection minted it (else a fresh id is minted)
- lease.acquire is last-writer-wins; ids not minted here -> 5300 error
- lease.release by a non-holder viewer id is IGNORED (stays human)
- bare release (no viewer_id, no force) is refused while a human holds
- force:true releases regardless
- public_view never exposes the raw holder id, only sha256(vid)[:12]
Lease state lives in THIS object, so it survives a plugin-app restart
(the real gateway outlives the dashboard) - that is what creates orphans.
"""
import asyncio, hashlib, json, secrets, time
from aiohttp import web

TOKEN = "tok-mock"


class MockUpstream:
    def __init__(self):
        self.holder = "agent"
        self.holder_id = None
        self.since = None
        self.reason = ""
        # display/ws connections: {conn_id: "clean" | "abrupt" | "open"}
        self.display_conns = {}
        self._next_conn = 0

    def public_view(self):
        vid = self.holder_id
        return {"holder": self.holder, "viewer_id": None,
                "viewer_hash": hashlib.sha256(vid.encode()).hexdigest()[:12] if vid else None,
                "since": self.since, "reason": self.reason}

    def snapshot(self):
        return {"running": True, "width": 1440, "height": 900,
                "lease": self.public_view(), "profile_key": "mock"}

    @staticmethod
    def _ok(rid, result):
        return {"jsonrpc": "2.0", "id": rid, "result": result}

    @staticmethod
    def _err(rid, msg):
        return {"jsonrpc": "2.0", "id": rid,
                "error": {"code": 5300, "message": msg,
                          "data": {"code": "viewer_mismatch"}}}

    async def index(self, request):
        return web.Response(
            text=f'<html><script>window.__HERMES_SESSION_TOKEN__ = "{TOKEN}";</script></html>',
            content_type="text/html")

    async def rpc_ws(self, request):
        if request.query.get("token") != TOKEN:
            return web.Response(status=401)
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        minted = set()  # per-connection minted ids (pinned semantics)
        async for msg in ws:
            if msg.type != web.WSMsgType.TEXT:
                continue
            try:
                frame = json.loads(msg.data)
            except ValueError:
                continue
            rid, method, p = frame.get("id"), frame.get("method"), frame.get("params") or {}
            if method == "display.status":
                await ws.send_str(json.dumps(self._ok(rid, self.snapshot())))
            elif method == "display.observe":
                req = str(p.get("viewer_id") or "").strip()
                vid = req if req in minted else secrets.token_urlsafe(16)
                minted.add(vid)
                await ws.send_str(json.dumps(self._ok(
                    rid, {"ticket": secrets.token_urlsafe(8),
                          "path": "/api/display/ws", "viewer_id": vid,
                          **self.snapshot()})))
            elif method == "display.lease.acquire":
                vid = str(p.get("viewer_id") or "").strip()
                if vid not in minted:
                    await ws.send_str(json.dumps(self._err(
                        rid, "viewer_id was not minted for this connection; call display.observe first")))
                    continue
                if not (self.holder == "human" and self.holder_id == vid):
                    self.holder, self.holder_id = "human", vid
                    self.since, self.reason = time.time(), str(p.get("reason") or "")
                await ws.send_str(json.dumps(self._ok(rid, {"lease": self.public_view()})))
            elif method == "display.lease.release":
                vid = str(p.get("viewer_id") or "").strip() or None
                force = bool(p.get("force"))
                if vid is not None and not force and vid not in minted:
                    await ws.send_str(json.dumps(self._err(
                        rid, "viewer_id was not minted for this connection; call display.observe first")))
                    continue
                if vid is None and not force and self.holder == "human":
                    await ws.send_str(json.dumps(self._err(
                        rid, "viewer_id required to release another viewer's lease (or pass force: true)")))
                    continue
                if vid is not None and self.holder == "human" and self.holder_id != vid:
                    pass  # pinned: release by non-holder is ignored, not an error
                elif self.holder == "human":
                    self.holder, self.holder_id = "agent", None
                    self.since, self.reason = time.time(), ""
                await ws.send_str(json.dumps(self._ok(rid, {"lease": self.public_view()})))
            else:
                await ws.send_str(json.dumps(self._err(rid, f"unknown method {method}")))
        return ws

    async def display_ws(self, request):
        """Echo server standing in for the RFB bridge; records close nature."""
        if "display_ticket" not in request.query:
            return web.Response(status=401)
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self._next_conn += 1
        cid = self._next_conn
        self.display_conns[cid] = "open"
        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.BINARY:
                    await ws.send_bytes(msg.data)
                elif msg.type == web.WSMsgType.TEXT:
                    await ws.send_str(msg.data)
            self.display_conns[cid] = "clean"  # peer closed politely
        except Exception:
            self.display_conns[cid] = "abrupt"
        return ws

    def app(self):
        a = web.Application()
        a.router.add_get("/", self.index)
        a.router.add_get("/api/ws", self.rpc_ws)
        a.router.add_get("/api/display/ws", self.display_ws)
        return a
