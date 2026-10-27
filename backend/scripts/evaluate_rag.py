"""Run the deterministic Phase 5 offline RAG regression harness.

The harness uses the real retrieval and RAG services with local lexical
embeddings, an in-memory store, and an extractive fake LLM. It is not a live
model-quality benchmark and does not assess claim-level entailment.

Example:
    python scripts/evaluate_rag.py
    python scripts/evaluate_rag.py --output evaluation/rag_last_run.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from evaluation.rag_harness import (  # noqa: E402
    DATASET_PATH,
    main as harness_main,
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DATASET_PATH,
        help="Path to the evaluation JSON dataset.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON file path to write results to.",
    )
    parser.add_argument(
        "--mode",
        choices=("semantic", "hybrid"),
        default="hybrid",
        help="Retrieval mode exercised by the harness.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    forwarded = ["--dataset", str(args.dataset), "--mode", args.mode]
    if args.output is not None:
        forwarded.extend(["--output", str(args.output)])
    return harness_main(forwarded)


if __name__ == "__main__":
    sys.exit(main())
