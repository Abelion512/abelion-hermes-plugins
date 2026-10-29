from __future__ import annotations

import json
import os
import subprocess
import textwrap
from pathlib import Path

SCREEN = Path(__file__).resolve().parents[1]


def _fake_hermes(tmp_path: Path, enabled: list[str]) -> tuple[Path, dict[str, str]]:
    home = tmp_path / ".hermes"
    (home / "plugins").mkdir(parents=True)
    (home / "config.yaml").write_text("plugins:\n  enabled: []\n", encoding="utf-8")
    (home / "enabled.txt").write_text("".join(f"{name}\n" for name in enabled), encoding="utf-8")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    cli = bin_dir / "hermes"
    cli.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env bash
            set -euo pipefail
            if [[ "$1" == config && "$2" == get && "$3" == plugins.enabled ]]; then
              if [[ -f "$HERMES_HOME/enabled.txt" ]]; then
                while IFS= read -r n; do printf -- '- %s\\n' "$n"; done < "$HERMES_HOME/enabled.txt"
              else
                echo "plugins.enabled not set"
              fi
            elif [[ "$1" == config && "$2" == set && "$3" == plugins.enabled ]]; then
              python3 - "$4" "$HERMES_HOME/enabled.txt" "$HERMES_HOME/last_set.json" <<'PY'
            import json, sys
            items = json.loads(sys.argv[1])
            with open(sys.argv[2], "w", encoding="utf-8") as f:
                f.write("".join(f"{item}\\n" for item in items))
            with open(sys.argv[3], "w", encoding="utf-8") as f:
                json.dump(items, f)
            PY
            else
              echo "unexpected Hermes CLI invocation: $*" >&2
              exit 2
            fi
            """
        ),
        encoding="utf-8",
    )
    cli.chmod(0o755)
    env = {
        **os.environ,
        "HOME": str(tmp_path),
        "HERMES_HOME": str(home),
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
    }
    return home, env


def _run(script: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCREEN / script)],
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


def test_install_and_uninstall_scripts_parse_as_bash() -> None:
    for script in ("install.sh", "uninstall.sh"):
        result = subprocess.run(
            ["bash", "-n", str(SCREEN / script)],
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, f"{script} failed bash -n:\\n{result.stderr}"


def test_install_preserves_existing_enabled_plugins_and_stages_files(tmp_path: Path) -> None:
    home, env = _fake_hermes(tmp_path, ["pii-mask-abelion"])

    result = _run("install.sh", env)

    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads((home / "last_set.json").read_text(encoding="utf-8")) == [
        "pii-mask-abelion",
        "screen",
    ]
    assert (home / "plugins" / "screen" / "plugin.yaml").read_text(encoding="utf-8").startswith("name: screen")
    assert (home / "plugins" / "screen" / "dashboard").is_dir()
    assert list((home / "plugins").glob(".screen-install.*")) == []
    assert list(home.glob("config.yaml.bak-screen-*"))


def test_uninstall_removes_only_screen_from_enabled_list(tmp_path: Path) -> None:
    home, env = _fake_hermes(tmp_path, ["pii-mask-abelion", "screen"])
    screen = home / "plugins" / "screen"
    screen.mkdir()
    (screen / "plugin.yaml").write_text("name: screen\ndescription: test\n", encoding="utf-8")

    result = _run("uninstall.sh", env)

    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads((home / "last_set.json").read_text(encoding="utf-8")) == ["pii-mask-abelion"]
    assert (home / "enabled.txt").read_text(encoding="utf-8") == "pii-mask-abelion\n"
    assert not screen.exists()
    assert (home / "plugins").is_dir()
    assert list(home.glob("config.yaml.bak-uninstall-*"))


def test_uninstall_refuses_unknown_directory_before_mutating_config(tmp_path: Path) -> None:
    home, env = _fake_hermes(tmp_path, ["pii-mask-abelion", "screen"])
    screen = home / "plugins" / "screen"
    screen.mkdir()
    (screen / "plugin.yaml").write_text("name: unrelated-plugin\n", encoding="utf-8")

    result = _run("uninstall.sh", env)

    assert result.returncode != 0
    assert screen.is_dir()
    assert (home / "enabled.txt").read_text(encoding="utf-8") == "pii-mask-abelion\nscreen\n"
    assert not (home / "last_set.json").exists()
