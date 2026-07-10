from __future__ import annotations

import argparse
import json

from app.candidates.selection_v2 import StrategySelectionV2Service


def main() -> None:
    parser = argparse.ArgumentParser(description="Run V2 strategy selection in simulation/review-only mode.")
    parser.add_argument("--mode", choices=["strict", "balanced", "exploratory"], default="balanced")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--date", dest="as_of_date", default=None)
    parser.add_argument("--write-artifacts", action="store_true")
    args = parser.parse_args()

    result = StrategySelectionV2Service().run(
        mode=args.mode,
        limit=args.limit,
        as_of_date=args.as_of_date,
        write_artifacts=args.write_artifacts,
    )
    print(json.dumps({
        "status": result["status"],
        "date": result["date"],
        "mode": result["mode"],
        "summary": result["summary"],
        "artifact_dir": result.get("artifact_dir"),
        "safety": result["safety"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
