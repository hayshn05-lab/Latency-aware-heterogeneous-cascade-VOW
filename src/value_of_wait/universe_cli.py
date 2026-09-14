"""CLI for the broad market-level trade/L2 coverage probe."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .client import MissingTokenError
from .replay_audit import ReplayValidationError
from .universe_probe import probe_market_universe


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe broad Polymarket REST replay coverage")
    parser.add_argument("--config", required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args(argv)
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    try:
        summary = probe_market_universe(config, Path(args.release), offline=args.offline)
    except MissingTokenError as error:
        print(str(error))
        return 2
    except (FileNotFoundError, ReplayValidationError, RuntimeError) as error:
        print(str(error))
        return 1
    print(json.dumps(summary, sort_keys=True))
    return 0
