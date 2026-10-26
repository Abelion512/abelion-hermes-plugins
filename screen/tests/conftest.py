"""Spin up the mock upstream (one per session, keeps lease state) and the
plugin FastAPI app (per test, restartable = a dashboard restart)."""
import asyncio, os, socket, sys, threading, time, types

import pytest

@pytest.fixture(autouse=True)
def _core_ws_auth_stub(monkeypatch):
    """hermes_cli is not installed in the test harness. Production now FAILS
    CLOSED when the core WS auth module is missing, so tests inject a stub
    that admits; the gate test replaces it with a denying one."""
    fake_chat = types.ModuleType("hermes_cli.web_server_chat")
    fake_chat._ws_auth_ok = lambda ws: True
    fake_pkg = types.ModuleType("hermes_cli")
    fake_pkg.web_server_chat = fake_chat
    monkeypatch.setitem(sys.modules, "hermes_cli", fake_pkg)
    monkeypatch.setitem(sys.modules, "hermes_cli.web_server_chat", fake_chat)


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "dashboard"))

from aiohttp import web  # noqa: E402
import uvicorn  # noqa: E402
from fastapi import FastAPI  # noqa: E402

from mock_ci import MockUpstream  # noqa: E402


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _run_aiohttp(app, port, ready):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    runner = web.AppRunner(app)
    loop.run_until_complete(runner.setup())
    loop.run_until_complete(web.TCPSite(runner, "127.0.0.1", port).start())
    ready.set()
    loop.run_forever()


class PluginServer:
    def __init__(self, upstream_port):
        self.upstream_port = upstream_port
        self.port = _free_port()
        self.server = None
        self.thread = None

    def start(self):
        import plugin_api  # imported here so env is set before first use
        app = FastAPI()
        app.include_router(plugin_api.router, prefix="/api/plugins/screen")
        cfg = uvicorn.Config(app, host="127.0.0.1", port=self.port,
                             log_level="error")
        self.server = uvicorn.Server(cfg)
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        for _ in range(100):
            if self.server.started:
                return
            time.sleep(0.05)
        raise RuntimeError("plugin app did not start")

    def stop(self):
        if self.server:
            self.server.should_exit = True
            self.thread.join(timeout=5)
        self.server = None

    def restart(self):
        """Abrupt dashboard restart: drop the process WITHOUT closing the
        upstream WS politely, so the mock keeps the orphaned human lease."""
        self.stop()


@pytest.fixture(scope="session")
def mock():
    m = MockUpstream()
    port = _free_port()
    ready = threading.Event()
    t = threading.Thread(target=_run_aiohttp, args=(m.app(), port, ready),
                         daemon=True)
    t.start()
    assert ready.wait(timeout=5)
    m.port = port
    m.base_ws = f"ws://127.0.0.1:{port}"
    return m


@pytest.fixture()
def plugin(mock):
    os.environ["HERMES_SCREEN_UPSTREAM"] = mock.base_ws
    # fresh module state per test: each plugin (re)start must not inherit
    # _rpc/_ticket/_viewer_id from a previous one
    import plugin_api
    plugin_api._rpc = None
    plugin_api._rpc_base = None
    plugin_api._ticket = None
    plugin_api._viewer_id = None
    srv = PluginServer(mock.port)
    srv.start()
    srv.base_http = f"http://127.0.0.1:{srv.port}"
    yield srv
    srv.stop()
