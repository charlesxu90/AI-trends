"""AI-Trend: automated topic assignment for AI-conference papers.

Deterministic core (taxonomy, substring assignment, spaCy candidate extraction)
plus the I/O glue for the AI-driven keyword-curation step. The reasoning step
itself lives in the ``curate-topics`` Claude Code skill; this package gives that
skill testable, reproducible tools to work with.
"""

from ai_trend.taxonomy import Taxonomy

__all__ = ["Taxonomy"]
__version__ = "0.1.0"
