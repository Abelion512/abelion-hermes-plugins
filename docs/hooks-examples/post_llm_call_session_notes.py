#!/usr/bin/env python3
"""Contoh hook post_llm_call: self-improving session capture.

Prinsip Anthropic: stop hook merefleksi sesi dan mengusulkan update CLAUDE.md.
Hermes adaptation: append ringkasan ke file scratchpad, jangan auto-edit .hermes.md/AGENTS.md.
Fail-open. Hook ini hanya log, bukan enforce.
"""
import os, sys, pathlib, datetime

def main():
    try:
        log_dir = pathlib.Path.home() / ".hermes" / "cache" / "scratch"
        log_dir.mkdir(parents=True, exist_ok=True)
        out = log_dir / "harness-session-notes.md"
        ts = datetime.datetime.now().isoformat(timespec="seconds")
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"- [{ts}] post_llm_call hook fired. Tinjau bila perlu update .hermes.md/AGENTS.md.\n")
    except Exception:
        pass
    return 0

if __name__ == "__main__":
    sys.exit(main())
