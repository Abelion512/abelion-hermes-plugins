"""The E2E subprocess environment must not inherit unrelated host credentials."""
from support.host import desktop_env, hermetic_env


def test_hermetic_environment_uses_allowlist(monkeypatch, tmp_path):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "must-not-cross-process-boundary")
    monkeypatch.setenv("SOME_PRIVATE_CREDENTIAL", "must-not-cross-process-boundary")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-cross-process-boundary")
    monkeypatch.setenv("NODE_PATH", "/tmp/e2e-node/node_modules")
    env = hermetic_env(tmp_path)
    assert env["HOME"] == str(tmp_path)
    assert env["HERMES_HOME"] == str(tmp_path / ".hermes")
    assert env["NODE_PATH"] == "/tmp/e2e-node/node_modules"
    assert "AWS_ACCESS_KEY_ID" not in env
    assert "SOME_PRIVATE_CREDENTIAL" not in env
    assert "OPENAI_API_KEY" not in env


def test_desktop_environment_adds_only_explicit_display_capabilities(monkeypatch, tmp_path):
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "must-not-cross-process-boundary")
    env = desktop_env(tmp_path, ":123", "/tmp/test.Xauthority")
    assert env["DISPLAY"] == ":123"
    assert env["XAUTHORITY"] == "/tmp/test.Xauthority"
    assert "AWS_SECRET_ACCESS_KEY" not in env
