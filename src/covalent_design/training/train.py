"""Task 24: Training smoke CLI entry point.

Usage::

    python -m covalent_design.training.train

Reads ``configs/covalent_train_smoke.yml`` and executes one smoke training
step, producing a single ``train_metrics.jsonl`` row.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main(argv: list[str] | None = None) -> None:
    """Run one smoke training step.

    The config file is resolved relative to the repository root (two
    directories above this module's package).
    """
    import covalent_design.training.train_loop as _loop

    parser = argparse.ArgumentParser(description="Run the Task 24 smoke training step.")
    parser.add_argument("--config", default=None, help="Path to smoke YAML config.")
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[3]
    config_path = (
        Path(args.config).resolve()
        if args.config
        else repo_root / "configs" / "covalent_train_smoke.yml"
    )

    if not config_path.exists():
        raise FileNotFoundError(f"config not found: {config_path}")

    report = _loop.run_smoke_train(str(config_path))

    # Print a concise JSON summary line to stdout
    import json as _json

    summary = {
        "step": report.step,
        "total_loss": report.total_loss,
        "components": report.components,
    }
    print(_json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
