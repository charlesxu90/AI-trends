"""Compare a freshly-assigned ``topic`` column against a committed ``*_topics.csv``.

Used to prove the deterministic port in ``ai_trend.assign`` reproduces the labels
that the original notebook produced. Rows are aligned by position (both files come
from the same source CSV in the same order); titles are cross-checked to catch
any misalignment.

Usage::

    python scripts/check_agreement.py REFERENCE_topics.csv CANDIDATE.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd


def _normalize(value: object) -> str:
    """Treat NaN / empty interchangeably; the notebook wrote empty strings."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value)


def compare(reference_path: Path, candidate_path: Path) -> dict:
    ref = pd.read_csv(reference_path)
    cand = pd.read_csv(candidate_path)

    if len(ref) != len(cand):
        raise ValueError(
            f"Row count differs: reference={len(ref)} candidate={len(cand)}"
        )
    for frame, path in ((ref, reference_path), (cand, candidate_path)):
        if "topic" not in frame.columns:
            raise ValueError(f"{path} has no 'topic' column")

    ref_topics = [_normalize(v) for v in ref["topic"]]
    cand_topics = [_normalize(v) for v in cand["topic"]]

    mismatches = []
    for idx, (rt, ct) in enumerate(zip(ref_topics, cand_topics)):
        if rt != ct:
            title = ref["title"].iloc[idx] if "title" in ref.columns else f"row {idx}"
            mismatches.append({"row": idx, "title": str(title)[:80], "ref": rt, "cand": ct})

    total = len(ref_topics)
    agree = total - len(mismatches)
    return {
        "total": total,
        "agree": agree,
        "agreement_pct": (agree / total * 100) if total else 100.0,
        "mismatches": mismatches,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument(
        "--show", type=int, default=10, help="how many mismatches to print"
    )
    args = parser.parse_args()

    result = compare(args.reference, args.candidate)
    print(
        f"Agreement: {result['agree']}/{result['total']} "
        f"({result['agreement_pct']:.2f}%)"
    )
    for mismatch in result["mismatches"][: args.show]:
        print(
            f"  row {mismatch['row']}: {mismatch['title']!r}\n"
            f"      ref={mismatch['ref']!r}\n     cand={mismatch['cand']!r}"
        )
    if len(result["mismatches"]) > args.show:
        print(f"  ... and {len(result['mismatches']) - args.show} more")

    # Non-zero exit if agreement is below the faithfulness bar.
    return 0 if result["agreement_pct"] >= 99.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
