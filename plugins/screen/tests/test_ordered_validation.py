"""Screen request-shape tests: invalid lease intents must stop before any upstream RPC."""
import asyncio
from unittest.mock import patch

import pytest
import plugin_api


class Request:
    def __init__(self, raw):
        self.raw = raw

    async def body(self):
        return self.raw


@pytest.mark.parametrize(
    "action,body",
    [
        ("release", b"{"),
        ("release", b"[]"),
        ("release", b'{"force":"false"}'),
        ("acquire", b'{"force":true}'),
        ("release", b'{"unknown":1}'),
    ],
)
def test_screen_wrong_requirement_no_rpc(action, body):
    plugin_api._viewer_id = "mine"
    with patch.object(plugin_api, "_rpc_call", side_effect=AssertionError("must not call upstream")):
        result = asyncio.run(plugin_api.lease(Request(body), action))
        assert result.status_code == 422


def test_screen_explicit_force_release_only():
    plugin_api._viewer_id = "mine"
    plugin_api._rpc = None
    calls = []

    async def rpc(request, method, params=None):
        calls.append((method, params))
        return {"lease": {"holder": "agent"}}

    with patch.object(plugin_api, "_rpc_call", side_effect=rpc):
        result = asyncio.run(plugin_api.lease(Request(b'{"force":true}'), "release"))
    assert calls == [("display.lease.release", {"force": True})]
    assert result["forced"] is True
