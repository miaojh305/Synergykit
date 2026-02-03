#!/usr/bin/env python3
"""SynergyKit CLI — run a synergy analysis from a JSON input file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from synergykit.schema import DealInput
from synergykit.engine import run
from synergykit.memo import generate


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SynergyKit — M&A synergy analysis CLI",
    )
    parser.add_argument(
        "input_file",
        type=Path,
        help="Path to a JSON deal input file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory for output files (default: ./output).",
    )
    args = parser.parse_args()

    # --- Load and validate input ---
    input_path: Path = args.input_file
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    try:
        raw = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON in {input_path}: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        deal = DealInput(**raw)
    except ValidationError as e:
        print(f"Error: input validation failed:\n{e}", file=sys.stderr)
        sys.exit(1)

    # --- Run engine ---
    result = run(deal)

    # --- Write outputs ---
    out_dir: Path = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / "synergy_schedule.csv"
    result.synergy_schedule.to_csv(csv_path, index=False)

    memo_path = out_dir / "deal_memo.md"
    memo_path.write_text(generate(deal, result), encoding="utf-8")

    summary_path = out_dir / "summary.csv"
    import pandas as pd
    pd.DataFrame([result.summary]).to_csv(summary_path, index=False)

    print(f"Done. Outputs written to {out_dir}/")
    print(f"  - {csv_path.name}   (annual synergy schedule)")
    print(f"  - {summary_path.name}      (scalar summary metrics)")
    print(f"  - {memo_path.name}     (Markdown deal memo)")


if __name__ == "__main__":
    main()
