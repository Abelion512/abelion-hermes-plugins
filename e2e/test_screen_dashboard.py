"""Screen plugin, real flow: real dashboard + real Bot Desktop (Xvnc/XFCE) + real Chrome.

Requirements (otherwise NOT RUN, with the missing item named): Xvnc and xdotool on PATH, node with
puppeteer-core resolvable (NODE_PATH), a Chrome (SCREEN_E2E_CHROME or google-chrome), HERMES_PYTHON.
Host caveat: Bot Desktop refuses to start below its free-memory guard; SCREEN_E2E_MIN_FREE_MB lowers it
for constrained CI hosts only (reported by the test, never a default).
Not covered: model-driven computer_use, phone/Tailscale, abrupt tab close, a user's own desktop.
"""
import json, os, shutil, signal, socket, subprocess, sys, time, urllib.request
from pathlib import Path
import pytest
from support.host import HERMES_PYTHON, OFFER, PLUGINS, desktop_env, hermetic_env

CHROME = os.environ.get("SCREEN_E2E_CHROME") or shutil.which("google-chrome") or ""
NODE = shutil.which("node")
DRIVER = Path(__file__).parent / "support" / "screen_driver.js"


def _missing():
    m = []
    if OFFER is None: m.append("Hermes (HERMES_PYTHON)")
    for t in ("Xvnc", "xdotool", "xfce4-terminal"):
        if not shutil.which(t): m.append(t)
    if not NODE: m.append("node")
    elif subprocess.run([NODE, "-e", "require('puppeteer-core')"], capture_output=True).returncode: m.append("puppeteer-core (NODE_PATH)")
    if not CHROME: m.append("chrome (SCREEN_E2E_CHROME)")
    return m


MISSING = _missing()
if os.environ.get("REQUIRE_SCREEN_E2E") == "1" and MISSING:
    raise RuntimeError("Screen E2E is required in CI; missing prerequisites: " + ", ".join(MISSING))
pytestmark = pytest.mark.skipif(bool(MISSING), reason="NOT RUN: missing " + ", ".join(MISSING))


@pytest.fixture(scope="module")
def flow(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("screen"); home = tmp / "home"; h = home / ".hermes"; (h / "plugins").mkdir(parents=True)
    shutil.copytree(PLUGINS / "screen", h / "plugins" / "screen", ignore=shutil.ignore_patterns("tests", "__pycache__"))
    cfg = f"plugins:\n  enabled: [screen]\ntelemetry:\n  shared_metrics:\n    enabled: false\n    send: false\n    offer_version: {OFFER}\n"
    if os.environ.get("SCREEN_E2E_MIN_FREE_MB"): cfg += f"bot_desktop:\n  min_free_memory_mb: {int(os.environ['SCREEN_E2E_MIN_FREE_MB'])}\n"
    (h / "config.yaml").write_text(cfg)
    env = hermetic_env(home)
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    dashboard_log = tmp / "dashboard.log"
    with dashboard_log.open("w", encoding="utf-8") as log:
        dash = subprocess.Popen(
            [HERMES_PYTHON, "-m", "hermes_cli.main", "dashboard", "--port", str(port), "--no-open", "--skip-build", "--isolated"],
            env=env, stdout=log, stderr=subprocess.STDOUT, text=True, start_new_session=True)
    try:
        for _ in range(60):
            if dash.poll() is not None:
                break
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/screen", timeout=2) as response:
                    if response.status < 500:
                        break
            except Exception:
                time.sleep(1)
        else:
            tail = dashboard_log.read_text(encoding="utf-8", errors="replace")[-5000:]
            pytest.fail(f"dashboard did not serve /screen (exit={dash.poll()}); log:\\n{tail}")
        if dash.poll() is not None:
            tail = dashboard_log.read_text(encoding="utf-8", errors="replace")[-5000:]
            pytest.fail(f"dashboard exited before becoming ready (exit={dash.returncode}); log:\\n{tail}")
        bd = h / "bot-desktop"
        def run():  # desktop state is created on Connect; driver reads display lazily
            display = ":" + ((bd / "display").read_text().strip() if (bd / "display").exists() else "20")
            return subprocess.run(
                [NODE, str(DRIVER), f"http://127.0.0.1:{port}/screen?profile=current", CHROME, str(tmp / "mk_"),
                 str(bd / "Xauthority"), display],
                capture_output=True, text=True, timeout=120,
                env=desktop_env(home, display, str(bd / "Xauthority")),
            )
        st = subprocess.run([HERMES_PYTHON, "-c", "from tools.bot_desktop import runtime as r; print(r.start(wait_seconds=60))"],
                            env=env, capture_output=True, text=True, timeout=120)
        if st.returncode: pytest.fail("desktop did not start: " + st.stderr[-300:])
        disp = ":" + (bd / "display").read_text().strip()
        term = subprocess.Popen(
            ["xfce4-terminal"],
            env=desktop_env(home, disp, str(bd / "Xauthority")),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
        )
        time.sleep(4)
        r = run()
        payload = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {"error": r.stderr[-300:]}
        steps = payload.get("steps", {})
        if not steps.get("api_build_probe", {}).get("ok", True) or payload.get("http_errors"):
            # Print during fixture setup so Pytest attaches this evidence to call-phase failures.
            print("SCREEN E2E API diagnostics: " + json.dumps({
                "api_build_probe": steps.get("api_build_probe"),
                "http_errors": payload.get("http_errors", []),
            }, sort_keys=True))
            try:
                log_lines = dashboard_log.read_text(encoding="utf-8", errors="replace").splitlines()
                needles = ("Plugin screen", "plugin screen", "Failed to load plugin", "plugin API",
                           "Plugin not found", "refusing unsafe api", "skipping API mount",
                           "plugins.enabled", "not in plugins.enabled", "Mounted plugin API routes")
                selected = [line for line in log_lines if any(term in line for term in needles)]
                print("SCREEN dashboard backend diagnostics:\\n" + "\\n".join(selected[-60:]))
            except Exception as exc:
                print("SCREEN dashboard diagnostics unavailable: " + type(exc).__name__)
        yield payload
    finally:
        subprocess.run([HERMES_PYTHON, "-m", "hermes_cli.main", "dashboard", "--stop"], env=env, capture_output=True)
        if dash.poll() is None:
            os.killpg(dash.pid, signal.SIGTERM)
        subprocess.run([HERMES_PYTHON, "-c", "from tools.bot_desktop import runtime as r; r.stop()"], env=env, capture_output=True)
        subprocess.run(["pkill", "-f", f"{h}/bot-desktop"], capture_output=True)


def test_connect_shows_live_view_under_agent_lease(flow):
    assert "error" not in flow, flow
    assert flow["steps"]["connected_lease"] == "agent"


def test_typing_is_ignored_while_agent_holds_lease(flow):
    assert flow["steps"]["typed_under_agent_lease"] is False


def test_take_over_gives_human_lease_and_input_works(flow):
    assert flow["steps"]["takeover_lease"] == "human"
    assert flow["steps"]["typed_under_human_lease"] is True


def test_reconnect_keeps_human_lease(flow):
    assert flow["steps"]["reconnect_lease"] == "human" and flow["steps"]["typed_after_reconnect"] is True


def test_hand_back_restores_view_only(flow):
    assert flow["steps"]["handback_lease"] == "agent"
    assert flow["steps"]["typed_after_handback"] is False


def test_no_page_errors(flow):
    assert flow["pageerrors"] == []
