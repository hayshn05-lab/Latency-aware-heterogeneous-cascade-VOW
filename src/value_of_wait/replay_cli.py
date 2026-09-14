"""CLI for building or reconstructing the replayability starter release."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .client import MissingTokenError
from .replay_audit import ReplayValidationError
from .starter_dataset import build_starter_dataset


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Historical event-market-L2 replayability audit")
    parser.add_argument("command", choices=("build",))
    parser.add_argument("--config", required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args(argv)
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    try:
        summary = build_starter_dataset(
            config,
            Path(args.release),
            Path(args.output),
            offline=args.offline,
        )
    except MissingTokenError as error:
        print(str(error))
        return 2
    except (FileNotFoundError, ReplayValidationError, RuntimeError) as error:
        print(str(error))
        return 1
    print(json.dumps(summary, sort_keys=True))
    return 0
