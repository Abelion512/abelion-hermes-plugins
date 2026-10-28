"""9Router Catalog is disabled in this repo: not in the catalog, not synced; code kept."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def test_nine_router_not_in_catalog_or_installer():
    ids = [p["id"] for p in json.loads((ROOT / "hermes.json").read_text())["plugins"]]
    assert "9router" not in ids and sorted(ids) == ["pii-mask-abelion", "screen"]
    sh = (ROOT / "update-plugins.sh").read_text()
    assert "rsync" in sh and not [l for l in sh.splitlines() if "9router" in l and not l.lstrip().startswith("#")]


def test_nine_router_code_kept():
    assert (ROOT / "model-providers" / "9router" / "plugin.yaml").is_file()
