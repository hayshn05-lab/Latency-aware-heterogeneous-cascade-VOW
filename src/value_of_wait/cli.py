"""Command line entry point; credentials are deliberately environment-only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .client import MissingTokenError
from .pipeline import run_pilot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Findata tweet-to-market latency pilot")
    parser.add_argument("command", choices=("audit", "run"))
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args(argv)
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    try:
        run_pilot(config, Path(args.output), offline=args.offline)
    except MissingTokenError as error:
        print(str(error))
        return 2
    return 0
