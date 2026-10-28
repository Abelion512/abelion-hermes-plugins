"""9Router Catalog is disabled in this repo; behavior of an already installed copy on a real Hermes."""
import json, shutil, subprocess
from pathlib import Path
from support.host import PLUGINS, HERMES_PYTHON, hermetic_env, make_profile, run_hermes, requires_hermes
from support.fake_provider import FakeProvider

pytestmark = requires_hermes


def test_repo_does_not_list_or_install_nine_router():
    ids = [p["id"] for p in json.loads((PLUGINS / "hermes.json").read_text())["plugins"]]
    assert "9router" not in ids
    sh = (PLUGINS / "update-plugins.sh").read_text()
    assert not [l for l in sh.splitlines() if "9router" in l and not l.lstrip().startswith("#")]
    assert (PLUGINS / "model-providers" / "9router" / "plugin.yaml").is_file()


def _registered(home):
    code = 'import providers;print(any(getattr(p,"name","")=="9router" for p in providers.list_providers()))'
    r = subprocess.run([HERMES_PYTHON, "-c", code], env=hermetic_env(home), capture_output=True, text=True)
    return r.stdout.strip().splitlines()[-1] == "True"


def test_installed_copy_native_remove_unregisters_but_disable_does_not(tmp_path):
    with FakeProvider() as srv:
        home = make_profile(tmp_path, srv.base_url)
        dst = home / ".hermes" / "plugins" / "model-providers"; dst.mkdir()
        shutil.copytree(PLUGINS / "model-providers" / "9router", dst / "9router")
        assert _registered(home) is True            # installed copy registers although not enabled
        run_hermes(home, ["plugins", "disable", "9router"])
        assert _registered(home) is True            # known gap: disable does not unregister
        run_hermes(home, ["plugins", "remove", "9router"])
        assert _registered(home) is False           # native remove is the only verified way off
