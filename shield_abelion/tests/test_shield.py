import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sg = importlib.import_module("shield_abelion.safety_guard")
ld = importlib.import_module("shield_abelion.loop_detector")


def test_new_absolute_file_can_be_created(tmp_path):
    target = str(tmp_path / "new.txt")
    assert sg.check_and_block_read_before_edit("write_file", {"path": target}, session_id="s") is None


def test_existing_file_still_needs_read(tmp_path):
    f = tmp_path / "old.txt"
    f.write_text("x")
    blocked = sg.check_and_block_read_before_edit("write_file", {"path": str(f)}, session_id="s2")
    assert blocked and blocked["action"] == "block"
    sg.record_read("s2", str(f))
    assert sg.check_and_block_read_before_edit("write_file", {"path": str(f)}, session_id="s2") is None


def test_relative_path_keeps_guard():
    blocked = sg.check_and_block_read_before_edit(
        "write_file", {"path": "definitely/not/here.txt"}, session_id="s3")
    assert blocked and blocked["action"] == "block"


def test_loop_is_per_session():
    ld.reset_detector()
    args = {"path": "a.py"}
    assert ld.check_and_block("read_file", args, session_id="A") is None
    assert ld.check_and_block("read_file", args, session_id="A") is None
    # another session repeating the same call must not trip A's counter
    assert ld.check_and_block("read_file", args, session_id="B") is None
    assert ld.check_and_block("read_file", args, session_id="A")["action"] == "block"


def test_loop_without_session_id_still_blocks():
    ld.reset_detector()
    for _ in range(2):
        assert ld.check_and_block("read_file", {"path": "z"}) is None
    assert ld.check_and_block("read_file", {"path": "z"})["action"] == "block"


def test_session_state_is_bounded():
    ld.reset_detector()
    for i in range(ld._MAX_SESSIONS + 20):
        ld.check_and_block("t", {"i": i}, session_id=f"s{i}")
    assert len(ld._detectors) == ld._MAX_SESSIONS


def test_safety_guard_still_blocks_dangerous():
    assert sg.check_and_block("terminal", {"command": "rm -rf /"})
    assert sg.check_and_block("terminal", {"command": "ls -la"}) is None


def test_snapshot_reports_per_session_detectors(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    ld.reset_detector()
    ld.check_and_block("read_file", {"p": 1}, session_id="A")
    ld.check_and_block("read_file", {"p": 2}, session_id="B")
    snap = ld.snapshot()
    assert snap["sessions"] == 2 and snap["history_size"] == 2 and snap["recent"]
