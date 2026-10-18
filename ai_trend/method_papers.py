"""Match corpus papers onto method-tree leaves and pick representatives.

Each leaf of ``config/ontology.json`` may list ``keywords``: phrases matched
case-insensitively, as whole words, against a paper's title + abstract (a
trailing ``s``/``es`` on a word still matches; ``^phrase`` matches the title
only). Per leaf and per year the site shows the top papers -- title matches
first, then by citations -- so the tree doubles as a filter for the most
representative papers of each research direction. Recomputed on every
``export-site`` (and therefore every ``refresh``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import quote

DEFAULT_PER_YEAR = 3
_SHORT_NAME_MAX = 32  # a "Name: subtitle" prefix longer than this is a sentence, not a name
_TOKEN_RE = re.compile(r"[a-z0-9]+")

# leaf index -> True if matched in the title, False if only in the abstract
LeafHits = dict[int, bool]


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(str(text or "").lower())


@dataclass(frozen=True)
class Matcher:
    """Phrases indexed by their first token: token -> ((phrase, title_only, leaf), ...)."""

    by_first: dict[str, tuple[tuple[tuple[str, ...], bool, int], ...]]


def _leaves(nodes: list[dict]) -> list[dict]:
    out: list[dict] = []
    for node in nodes:
        out.extend(_leaves(node["children"]) if node.get("children") else [node])
    return out


def compile_matcher(domains: list[dict]) -> Matcher:
    index: dict[str, list] = {}
    for i, leaf in enumerate(_leaves(domains)):
        for keyword in leaf.get("keywords", []):
            title_only = keyword.startswith("^")
            phrase = tuple(tokenize(keyword.lstrip("^")))
            if phrase:
                index.setdefault(phrase[0], []).append((phrase, title_only, i))
    return Matcher({k: tuple(v) for k, v in index.items()})


def _same(word: str, key: str) -> bool:
    return word == key or word == key + "s" or word == key + "es"


def _scan(matcher: Matcher, tokens: list[str], in_title: bool, hits: LeafHits) -> None:
    for i, tok in enumerate(tokens):
        keys = {tok, tok[:-1], tok[:-2]} if tok.endswith("s") else {tok}
        for key in keys:
            for phrase, title_only, leaf in matcher.by_first.get(key, ()):
                if title_only and not in_title:
                    continue
                if hits.get(leaf):  # already a title hit; nothing better possible
                    continue
                n = len(phrase)
                if len(tokens) - i >= n and all(_same(tokens[i + j], phrase[j]) for j in range(n)):
                    hits[leaf] = hits.get(leaf, False) or in_title


def match_leaves(matcher: Matcher, title: str, abstract: str) -> LeafHits:
    hits: LeafHits = {}
    _scan(matcher, tokenize(title), True, hits)
    _scan(matcher, tokenize(abstract), False, hits)
    return hits


def short_name(title: str) -> str:
    """'DUSt3R: Geometric 3D Vision Made Easy' -> 'DUSt3R'; otherwise the title."""
    head, sep, _ = title.partition(":")
    return head.strip() if sep and 0 < len(head.strip()) <= _SHORT_NAME_MAX else title


def paper_link(record: dict) -> str:
    if record.get("arxiv"):
        return f"https://arxiv.org/abs/{record['arxiv']}"
    if record.get("pdf"):
        return record["pdf"]
    return f"https://scholar.google.com/scholar?q={quote(record.get('title', ''))}"


def _paper_ref(record: dict) -> dict:
    ref = {
        "name": short_name(record["title"]),
        "title": record["title"],
        "conference": record["conference"],
        "url": paper_link(record),
    }
    if record.get("citations") is not None:
        ref["citations"] = record["citations"]
    return ref


def _rank_key(item: tuple[dict, bool]) -> tuple:
    record, in_title = item
    cites = record.get("citations")
    return (not in_title, -(cites if cites is not None else -1), record["title"])


def _leaf_papers(items: list[tuple[dict, bool]], per_year: int) -> list[dict]:
    by_year: dict[int, list[tuple[dict, bool]]] = {}
    for item in items:
        by_year.setdefault(item[0]["year"], []).append(item)
    return [
        {"year": year, "papers": [_paper_ref(r) for r, _ in sorted(group, key=_rank_key)[:per_year]]}
        for year, group in sorted(by_year.items(), reverse=True)
    ]


def _annotate(node: dict, leaf_items: list, counter: list[int], per_year: int) -> tuple[dict, set[int]]:
    """Return a copy of ``node`` with paper counts (and leaf papers), plus its paper-id set."""
    if node.get("children"):
        children, ids = [], set()
        for child in node["children"]:
            new_child, child_ids = _annotate(child, leaf_items, counter, per_year)
            children.append(new_child)
            ids |= child_ids
        return {**node, "children": children, "paper_count": len(ids)}, ids
    i = counter[0]
    counter[0] += 1
    unique = {pid: (rec, in_title) for pid, rec, in_title in leaf_items[i]}  # one entry per paper
    ids = set(unique)
    papers = _leaf_papers(list(unique.values()), per_year)
    return {**node, "paper_count": len(ids), "papers": papers}, ids


def site_ontology(
    ontology: dict,
    refs: dict,
    matched: Iterable[tuple[dict, LeafHits]],
    *,
    per_year: int = DEFAULT_PER_YEAR,
) -> dict:
    """New ontology dict for the site: method refs + per-node paper counts + per-leaf top papers."""
    n_leaves = len(_leaves(ontology["domains"]))
    leaf_items: list[list] = [[] for _ in range(n_leaves)]
    for record, hits in matched:
        pid = " ".join(tokenize(record["title"]))  # same paper listed twice -> one id
        for leaf, in_title in hits.items():
            leaf_items[leaf].append((pid, record, in_title))
    counter = [0]
    domains = [_annotate(d, leaf_items, counter, per_year)[0] for d in ontology["domains"]]
    return {**ontology, "domains": domains, "methods": dict(refs)}
