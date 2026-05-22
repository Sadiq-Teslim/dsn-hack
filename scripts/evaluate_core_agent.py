from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.evaluation.ablations import evaluate_agent_dataset_sync  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-path", type=Path, default=Path("data/amazon_subset"))
    parser.add_argument("--output", type=Path, default=Path("docs/core_evaluation_report.json"))
    parser.add_argument("--max-examples", type=int, default=100)
    args = parser.parse_args()
    report = evaluate_agent_dataset_sync(args.data_path, args.output, args.max_examples)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
