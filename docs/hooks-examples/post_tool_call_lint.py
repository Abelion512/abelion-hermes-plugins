#!/usr/bin/env python3
"""Contoh hook post_tool_call: lint file Python yang baru ditulis.

Prinsip Anthropic: hooks untuk aturan deterministik (lint/format), bukan prompt.
Hermes adaptation: script fail-open, jangan block tool call kecuali guard keamanan.
Registrasi: tambahkan ke hooks.post_tool_call di config.yaml setelah hermes config edit.

Env yang tersedia: CLAUDE_PROJECT_DIR tidak ada di Hermes; hook menerima JSON via stdin sesuai runtime.
Contoh ini hanya contoh; adaptasikan parsing payload sesuai hermes hooks dokumentasi.
"""
import os, sys, json, subprocess, pathlib

def main():
    try:
        # Hermes dapat mengirim payload lewat stdin; toleransi kosong.
        data = sys.stdin.read() if not sys.stdin.isatty() else ""
        # Ambil path file bila ada di payload, dukung beberapa bentuk field.
        paths = []
        if data:
            try:
                obj = json.loads(data)
                for k in ("file_path", "path", "filename"):
                    v = obj.get(k) if isinstance(obj, dict) else None
                    if v:
                        paths.append(v)
            except Exception:
                pass
        # Fallback env / cwd: tidak lint semua repo, hanya jika path eksplisit.
        cwd = pathlib.Path.cwd()
        for p in paths:
            fp = (cwd / p) if not pathlib.Path(p).is_absolute() else pathlib.Path(p)
            if fp.suffix == ".py" and fp.exists():
                # ruff format check saja; --fix bila repo mengizinkan.
                subprocess.run(["ruff", "check", str(fp)], timeout=10, capture_output=True)
    except Exception:
        pass  # fail-open
    return 0

if __name__ == "__main__":
    sys.exit(main())
