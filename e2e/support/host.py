"""Run a REAL Hermes process in an isolated profile against a loopback provider.

Requirements (tests are skipped, i.e. NOT RUN, when missing):
  HERMES_PYTHON  interpreter of a Hermes install (default: current interpreter, must import hermes_cli)
"""
import json, os, shutil, subprocess, sys
from pathlib import Path
import pytest

PLUGINS = Path(__file__).resolve().parents[2]
HERMES_PYTHON = os.environ.get("HERMES_PYTHON", sys.executable)


def _probe(code):
    r = subprocess.run([HERMES_PYTHON, "-c", code], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


OFFER = _probe("from hermes_cli.observability.shared_metrics_consent import OFFER_VERSION as v;print(v)")
HERMES_COMMIT = _probe("import subprocess,hermes_cli,os;d=os.path.dirname(os.path.dirname(hermes_cli.__file__));print(subprocess.run(['git','-C',d,'rev-parse','HEAD'],capture_output=True,text=True).stdout.strip())")
requires_hermes = pytest.mark.skipif(OFFER is None, reason="NOT RUN: no Hermes install importable via HERMES_PYTHON")


def hermetic_env(home: Path, extra=None):
    env = {k: v for k, v in os.environ.items() if not (k.endswith(("_API_KEY", "_TOKEN", "_SECRET", "_PASSWORD"))
           or k.startswith(("HERMES_", "OPENAI", "ANTHROPIC", "OPENROUTER", "GEMINI", "GOOGLE_")))}
    env.update(HOME=str(home), HERMES_HOME=str(home / ".hermes"), NO_COLOR="1", TERM="dumb",
               NO_PROXY="127.0.0.1,localhost", HERMES_ACCEPT_HOOKS="1", HERMES_STATE_DB_GUARD_BYPASS="1")
    env.update(extra or {})
    return env


def make_profile(tmp: Path, base_url: str, plugins=(), extra_config=""):
    """Profile whose only model endpoint is the loopback provider. Plugins are copied from this repo."""
    home = tmp / "home"; h = home / ".hermes"; h.mkdir(parents=True)
    enabled = "".join(f"    - {pid}\n" for pid, _ in plugins)
    (h / "config.yaml").write_text(
        f"model:\n  provider: custom\n  base_url: {base_url}\n  default: e2e-test-model\n  context_length: 128000\n"
        "agent:\n  api_max_retries: 1\nupdates:\n  check: false\ncompression:\n  enabled: false\n"
        f"telemetry:\n  shared_metrics:\n    enabled: false\n    send: false\n    offer_version: {OFFER}\n"
        + (f"plugins:\n  enabled:\n{enabled}" if plugins else "") + extra_config)
    (h / ".env").write_text("OPENAI_API_KEY=e2e-loopback-test-placeholder\n")
    (h / "plugins").mkdir()
    for pid, folder in plugins:
        shutil.copytree(PLUGINS / folder, h / "plugins" / pid, ignore=shutil.ignore_patterns("tests", "__pycache__"))
    return home


def run_hermes(home: Path, argv, timeout=100, extra_env=None, cwd=None):
    return subprocess.run([HERMES_PYTHON, "-m", "hermes_cli.main", *argv], env=hermetic_env(home, extra_env),
                          cwd=str(cwd or home), capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)


def wire_text(req) -> str:
    return json.dumps(req["body"], ensure_ascii=False)
