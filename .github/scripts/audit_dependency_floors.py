#!/usr/bin/env python3
"""Extract auditable minimum versions from PEP 440 requirements."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml
from packaging.requirements import Requirement
from packaging.version import Version


def dependency_floor(spec: str, environment: dict[str, str] | None = None) -> str | None:
    requirement = Requirement(spec)
    if requirement.url:
        raise ValueError(f"direct URL requirement has no auditable version floor: {spec}")
    if requirement.marker and not requirement.marker.evaluate(environment):
        return None

    candidates: list[Version] = []
    for item in requirement.specifier:
        op = item.operator
        raw_version = item.version
        if op == ">":
            raise ValueError(
                f"exclusive lower bound is not safely floor-auditable: {spec!r}; "
                "use >= with a deliberate minimum or add an explicit review"
            )
        if op in {">=", "==", "~="}:
            if "*" in raw_version:
                raise ValueError(f"unsupported lower-bound specifier in {spec!r}: {item}")
            try:
                candidates.append(Version(raw_version))
            except Exception as exc:
                raise ValueError(f"invalid PEP 440 lower-bound version in {spec!r}") from exc
        elif op in {"!=", "<", "<="}:
            continue
        elif op == "===":
            raise ValueError(f"arbitrary equality is not safely floor-auditable: {spec!r}")
        else:
            raise ValueError(f"unsupported PEP 440 operator {op!r} in {spec!r}")

    if not candidates:
        return None

    floor = max(candidates)
    if not requirement.specifier.contains(floor, prereleases=True):
        raise ValueError(
            f"computed boundary {floor} is excluded by the full specifier set in {spec!r}"
        )

    extras = f"[{','.join(sorted(requirement.extras))}]" if requirement.extras else ""
    return f"{requirement.name}{extras}=={floor}"


def manifest_floors(path: Path) -> list[str]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: plugin manifest must be a mapping")
    dependencies = data.get("python_dependencies", [])
    if dependencies is None:
        return []
    if not isinstance(dependencies, list) or any(not isinstance(x, str) for x in dependencies):
        raise ValueError(f"{path}: python_dependencies must be a list of strings")

    floors = []
    for spec in dependencies:
        floor = dependency_floor(spec)
        if floor:
            floors.append(floor)
    return sorted(set(floors), key=str.lower)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        floors = manifest_floors(args.manifest)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"::error title=dependency floor::{exc}", file=sys.stderr)
        return 2

    args.output.write_text("".join(item + "\n" for item in floors), encoding="utf-8")
    if not floors:
        print(f"{args.manifest}: no inclusive dependency floors to audit")
    else:
        print("Auditable dependency floors:")
        for floor in floors:
            print(f"  {floor}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
