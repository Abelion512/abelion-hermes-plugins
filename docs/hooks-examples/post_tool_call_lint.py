#!/usr/bin/env python3
"""Fail-open post_tool_call example that emits lint diagnostics to stderr."""
import json
import pathlib
import subprocess
import sys


def diagnostic(message: str) -> None:
    print(f"[post_tool_call_lint] {message}", file=sys.stderr)


def main() -> int:
    try:
        raw = sys.stdin.read() if not sys.stdin.isatty() else ""
        if not raw.strip():
            return 0
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            diagnostic(f"ignored invalid hook JSON: {exc}")
            return 0
        if not isinstance(payload, dict):
            diagnostic("ignored hook payload: expected a JSON object")
            return 0

        paths = [
            payload[key] for key in ("file_path", "path", "filename")
            if isinstance(payload.get(key), str) and payload[key].strip()
        ]
        cwd = pathlib.Path.cwd()
        for value in paths:
            candidate = pathlib.Path(value)
            target = candidate if candidate.is_absolute() else cwd / candidate
            if target.suffix != ".py" or not target.is_file():
                continue
            try:
                result = subprocess.run(
                    ["ruff", "check", str(target)],
                    check=False, capture_output=True, text=True, timeout=10,
                )
            except FileNotFoundError:
                diagnostic("ruff is not installed; lint was not run")
                return 0
            except subprocess.TimeoutExpired:
                diagnostic(f"ruff timed out for {target}; tool call remains successful")
                continue
            if result.returncode:
                diagnostic(f"ruff check reported issues for {target} (exit {result.returncode})")
                for line in (result.stdout + result.stderr).splitlines():
                    diagnostic(line)
    except Exception as exc:
        # The example is fail-open, but failures must remain visible.
        diagnostic(f"hook error ({type(exc).__name__}): {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
