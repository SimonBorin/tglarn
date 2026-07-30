#!/usr/bin/env python3
"""Calculate the next stable SemVer from repository tags."""

from __future__ import annotations

import argparse
import re
import subprocess
from collections.abc import Iterable, Sequence

SEMVER_PATTERN = re.compile(r"^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
INITIAL_VERSION = (0, 1, 0)
BUMP_TYPES = ("patch", "minor", "major")


def parse_version(value: str) -> tuple[int, int, int] | None:
    match = SEMVER_PATTERN.fullmatch(value.strip())
    if match is None:
        return None
    return tuple(int(part) for part in match.groups())


def latest_version(tags: Iterable[str]) -> tuple[int, int, int] | None:
    versions = (version for tag in tags if (version := parse_version(tag)) is not None)
    return max(versions, default=None)


def bump_version(version: tuple[int, int, int], bump: str) -> tuple[int, int, int]:
    major, minor, patch = version
    if bump == "patch":
        return major, minor, patch + 1
    if bump == "minor":
        return major, minor + 1, 0
    if bump == "major":
        return major + 1, 0, 0
    raise ValueError(f"Unsupported bump type: {bump}")


def next_version(tags: Iterable[str], bump: str) -> str:
    current = latest_version(tags) or INITIAL_VERSION
    return ".".join(str(part) for part in bump_version(current, bump))


def repository_tags() -> list[str]:
    result = subprocess.run(
        ["git", "tag", "--list"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bump", choices=BUMP_TYPES, default="patch")
    args = parser.parse_args(argv)
    print(next_version(repository_tags(), args.bump))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
