#!/usr/bin/env python3
"""Configure the public OAuth client ID used by the ZenMux Hermes plugin."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from pathlib import Path

CLIENT_ID_PATTERN = re.compile(r"^zpc_[A-Za-z0-9_-]+$")


def write_config(plugin_dir: Path, client_id: str) -> Path:
    """Validate and atomically persist a public client ID."""
    if not CLIENT_ID_PATTERN.fullmatch(client_id):
        raise ValueError("client ID must match zpc_[A-Za-z0-9_-]+")

    destination = plugin_dir / "zenmux.json"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".zenmux.", suffix=".json", dir=plugin_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump({"client_id": client_id}, output, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
    return destination


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("client_id", help="dedicated ZenMux public OAuth client ID")
    parser.add_argument(
        "--plugin-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "zenmux_hermes_plugin",
        help="installed ZenMux plugin directory",
    )
    args = parser.parse_args()
    destination = write_config(args.plugin_dir.resolve(), args.client_id)
    print(f"Configured ZenMux OAuth client in {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
