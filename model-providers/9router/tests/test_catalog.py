"""9Router live-catalog validation. No network or real provider is required."""
import importlib.util
import json
import urllib.request
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1] / "__init__.py"


class _Response:
    def __init__(self, raw):
        self.raw = raw

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return self.raw if size < 0 else self.raw[:size]


def _load(monkeypatch):
    # Prevent import-time registration from probing a real local gateway.
    def no_network(*args, **kwargs):
        raise OSError("network disabled in test")
    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    spec = importlib.util.spec_from_file_location("ninerouter_catalog_test", PLUGIN)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_offline_catalog_never_advertises_unverified_ids(monkeypatch):
    module = _load(monkeypatch)
    monkeypatch.setattr(module, "_fetch_models", lambda: None)
    module._discovered = None
    module._discovered_at = 0
    assert module.get_available_models() == []


def test_live_catalog_keeps_unique_valid_ids_only(monkeypatch):
    module = _load(monkeypatch)
    payload = json.dumps({"data": [
        {"id": "openai/gpt-test"}, {"id": "openai/gpt-test"},
        {"id": "qwen3:coder"}, {"id": "invalid model"}, {"id": 42}, {},
    ]}).encode()
    monkeypatch.setattr(module.urllib.request, "urlopen", lambda *a, **k: _Response(payload))
    assert module._fetch_models() == ["openai/gpt-test", "qwen3:coder"]


def test_live_catalog_response_size_is_bounded(monkeypatch):
    module = _load(monkeypatch)
    monkeypatch.setattr(module.urllib.request, "urlopen", lambda *a, **k: _Response(b"x" * 1_048_577))
    assert module._fetch_models() is None
