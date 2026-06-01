"""Migrate the curated taxonomy + noise blocklist out of ``1.assign_topics.ipynb``.

The notebook builds two structures incrementally across many cells:

* ``topic2keywords`` -- ``dict[str, list[str]]`` mapping a curated topic label to
  the keyword fragments that imply it.
* ``useless_kw`` -- ``set[str]`` of noise keywords to ignore.

This script executes *only* the dict-building cells (it stops before any cell that
reads a CSV or invokes spaCy) and dumps the final structures to JSON. Running the
notebook code -- rather than retyping the dicts -- guarantees the JSON is a faithful
reproduction of what produced the committed ``*_topics.csv`` files.

Usage::

    python scripts/migrate_notebook_taxonomy.py [--notebook PATH] [--out-dir DIR]
"""

from __future__ import annotations

import argparse
import json
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_NOTEBOOK = REPO_ROOT / "1.assign_topics.ipynb"
DEFAULT_OUT_DIR = REPO_ROOT / "config"

# The taxonomy is fully built before the first cell that reads a CSV. We stop
# there. ``read_csv`` is the reliable marker: it appears only in real I/O cells,
# never in the taxonomy/def cells (matching call names like ``assign_topics(``
# would wrongly halt on the harmless ``def`` cells that precede later additions).
STOP_MARKERS = ("read_csv",)


def _install_stub_modules() -> None:
    """Stub heavy deps so the dict-building cells import cleanly.

    The taxonomy cells only need plain Python, but the notebook imports spaCy at
    module scope. We never call into it (we stop before any spaCy use), so a stub
    is sufficient and keeps this script dependency-free.
    """
    if "spacy" not in sys.modules:
        spacy_stub = types.ModuleType("spacy")
        spacy_stub.displacy = types.ModuleType("spacy.displacy")
        spacy_stub.load = lambda *a, **k: None  # never called here
        sys.modules["spacy"] = spacy_stub
        sys.modules["spacy.displacy"] = spacy_stub.displacy


def _read_code_cells(notebook_path: Path) -> list[str]:
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    return [
        "".join(cell["source"])
        for cell in notebook.get("cells", [])
        if cell.get("cell_type") == "code"
    ]


def build_taxonomy(notebook_path: Path) -> tuple[dict[str, list[str]], set[str]]:
    """Execute the taxonomy-building cells and return ``(topic2keywords, useless_kw)``."""
    _install_stub_modules()
    namespace: dict[str, object] = {}
    executed = 0
    for cell in _read_code_cells(notebook_path):
        if any(marker in cell for marker in STOP_MARKERS):
            break
        exec(compile(cell, "<notebook-cell>", "exec"), namespace)  # noqa: S102
        executed += 1

    if "topic2keywords" not in namespace or "useless_kw" not in namespace:
        raise RuntimeError(
            "Notebook did not define topic2keywords / useless_kw before the first "
            f"I/O cell (executed {executed} cells). Did the notebook structure change?"
        )

    topic2keywords = namespace["topic2keywords"]
    useless_kw = namespace["useless_kw"]
    if not isinstance(topic2keywords, dict) or not isinstance(useless_kw, set):
        raise TypeError("Unexpected types for migrated taxonomy structures.")
    return topic2keywords, useless_kw


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notebook", type=Path, default=DEFAULT_NOTEBOOK)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    topic2keywords, useless_kw = build_taxonomy(args.notebook)

    taxonomy = {
        topic: _dedupe_preserve_order(list(keywords))
        for topic, keywords in topic2keywords.items()
    }
    blocklist = sorted(useless_kw)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    taxonomy_path = args.out_dir / "taxonomy.json"
    blocklist_path = args.out_dir / "useless_keywords.json"
    taxonomy_path.write_text(
        json.dumps(taxonomy, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    blocklist_path.write_text(
        json.dumps(blocklist, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(f"Wrote {len(taxonomy)} topics -> {taxonomy_path}")
    print(f"Wrote {len(blocklist)} noise keywords -> {blocklist_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
