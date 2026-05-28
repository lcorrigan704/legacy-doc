from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
TYPES = ROOT / "src" / "legacy_doc" / "types.py"
PARSER_VERSION_RE = re.compile(r'PARSER_VERSION = "([^"]+)"')


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync legacy_doc.types.PARSER_VERSION from pyproject.toml."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check versions match without editing files.",
    )
    args = parser.parse_args()

    package_version = _read_package_version()
    types_text = TYPES.read_text(encoding="utf-8")
    match = PARSER_VERSION_RE.search(types_text)
    if not match:
        print("PARSER_VERSION assignment not found in src/legacy_doc/types.py")
        return 1

    parser_version = match.group(1)
    if parser_version == package_version:
        print(f"Version is synced: {package_version}")
        return 0

    if args.check:
        print(
            "Version mismatch: "
            f"pyproject.toml has {package_version}, "
            f"types.py has {parser_version}"
        )
        return 1

    updated = PARSER_VERSION_RE.sub(
        f'PARSER_VERSION = "{package_version}"',
        types_text,
        count=1,
    )
    TYPES.write_text(updated, encoding="utf-8")
    print(f"Updated PARSER_VERSION from {parser_version} to {package_version}")
    return 0


def _read_package_version() -> str:
    with PYPROJECT.open("rb") as file:
        data = tomllib.load(file)
    return data["project"]["version"]


if __name__ == "__main__":
    sys.exit(main())
