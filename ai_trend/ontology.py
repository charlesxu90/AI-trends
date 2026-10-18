"""The method ontology: a hierarchical tree of AI methods by primary contribution.

Single source of truth is ``config/ontology.json``::

    {"version"?: str,
     "domains": [{"code"?, "name", "summary"?, "children": [
        {"name", "children": [{"name", "examples"?: [str, ...]}, ...]}, ...]}],
     "facets"?: [{"name", "tags": [str, ...]}],   # cross-cutting tag groups
     "heuristics"?: [str, ...]}                   # how to pick a paper's node

Leaves may carry ``keywords`` (see :mod:`ai_trend.method_papers`) used to match
corpus papers. Example methods are backed by ``config/method_refs.json``:
``{method: {"title", "year", "url"?}}`` -- the landmark paper, its year and link.

Domains (e.g. ``GEN`` Generation & synthesis) split into task families (Image
generation & editing) and then specific tasks (Text-to-image) with a few
representative example methods. Any node may carry ``code``, ``summary``,
``examples``, and ``children``; sibling names must be unique so a node's path
(``Generation > Image > Text-to-image``) identifies it. Facets (modality, model
family, application domain, ...) are tags kept outside the tree on purpose.
"""

from __future__ import annotations

import json
from pathlib import Path

ONTOLOGY_FILENAME = "ontology.json"
DEFAULT_ONTOLOGY_PATH = Path(__file__).resolve().parent.parent / "config" / ONTOLOGY_FILENAME
DEFAULT_METHOD_REFS_PATH = DEFAULT_ONTOLOGY_PATH.with_name("method_refs.json")
_ALLOWED_KEYS = {"code", "name", "summary", "examples", "keywords", "children"}
_TOP_LEVEL_KEYS = {"version", "domains", "facets", "heuristics"}


class OntologyError(ValueError):
    """Raised when ontology data is structurally invalid."""


def _clean_node(node: object, parent_path: tuple[str, ...]) -> dict:
    """Validate one node (recursively) and return a fresh, normalized copy."""
    where = " > ".join(parent_path) or "<root>"
    if not isinstance(node, dict):
        raise OntologyError(f"{where}: node must be an object")
    name = node.get("name")
    if not isinstance(name, str) or not name.strip():
        raise OntologyError(f"{where}: node needs a non-empty 'name'")
    path = (*parent_path, name.strip())
    here = " > ".join(path)
    unknown = set(node) - _ALLOWED_KEYS
    if unknown:
        raise OntologyError(f"{here}: unknown key(s) {sorted(unknown)}")

    clean: dict = {"name": name.strip()}
    if "code" in node:
        if not isinstance(node["code"], str) or not node["code"].strip():
            raise OntologyError(f"{here}: 'code' must be a non-empty string")
        clean = {"code": node["code"].strip(), **clean}
    if "summary" in node:
        if not isinstance(node["summary"], str):
            raise OntologyError(f"{here}: 'summary' must be a string")
        clean["summary"] = node["summary"].strip()
    if "examples" in node:
        examples = node["examples"]
        if not isinstance(examples, list) or not all(isinstance(e, str) and e.strip() for e in examples):
            raise OntologyError(f"{here}: 'examples' must be a list of non-empty strings")
        clean["examples"] = [e.strip() for e in examples]
    if "keywords" in node:
        if not _is_str_list(node["keywords"]):
            raise OntologyError(f"{here}: 'keywords' must be a list of non-empty strings")
        clean["keywords"] = [k.strip().lower() for k in node["keywords"]]
    if "children" in node:
        clean["children"] = _clean_children(node["children"], path)
    return clean


def _clean_children(children: object, path: tuple[str, ...]) -> list[dict]:
    where = " > ".join(path) or "<root>"
    if not isinstance(children, list):
        raise OntologyError(f"{where}: 'children' must be a list")
    cleaned = [_clean_node(child, path) for child in children]
    names = [c["name"] for c in cleaned]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        raise OntologyError(f"{where}: duplicate sibling name(s) {dupes}")
    return cleaned


def _is_str_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) and v.strip() for v in value)


def _clean_facets(facets: object) -> list[dict]:
    if not isinstance(facets, list):
        raise OntologyError("'facets' must be a list")
    cleaned = []
    for facet in facets:
        if not isinstance(facet, dict) or set(facet) != {"name", "tags"}:
            raise OntologyError(f"facet must be an object with exactly 'name' and 'tags': {facet!r}")
        if not isinstance(facet["name"], str) or not facet["name"].strip() or not _is_str_list(facet["tags"]):
            raise OntologyError(f"facet needs a non-empty 'name' and a list of string 'tags': {facet!r}")
        cleaned.append({"name": facet["name"].strip(), "tags": [t.strip() for t in facet["tags"]]})
    return cleaned


def validate_ontology(data: object) -> dict:
    """Validate raw ontology JSON and return a new, normalized ontology dict."""
    if not isinstance(data, dict) or not isinstance(data.get("domains"), list):
        raise OntologyError("ontology must be an object with a 'domains' list")
    unknown = set(data) - _TOP_LEVEL_KEYS
    if unknown:
        raise OntologyError(f"ontology: unknown top-level key(s) {sorted(unknown)}")
    heuristics = data.get("heuristics", [])
    if not isinstance(heuristics, list) or (heuristics and not _is_str_list(heuristics)):
        raise OntologyError("'heuristics' must be a list of non-empty strings")
    clean: dict = {}
    if "version" in data:
        clean["version"] = str(data["version"])
    clean["domains"] = _clean_children(data["domains"], ())
    clean["facets"] = _clean_facets(data.get("facets", []))
    clean["heuristics"] = [h.strip() for h in heuristics]
    return clean


def _read_json(path: Path) -> object:
    if not path.exists():
        raise OntologyError(f"ontology file not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as err:
        raise OntologyError(f"{path}: invalid JSON ({err})") from err


def load_ontology(path: Path | str = DEFAULT_ONTOLOGY_PATH) -> dict:
    """Read and validate the ontology file."""
    return validate_ontology(_read_json(Path(path)))


def load_method_refs(path: Path | str = DEFAULT_METHOD_REFS_PATH) -> dict:
    """Read and validate ``{method: {"title", "year", "url"?}}``."""
    data = _read_json(Path(path))
    if not isinstance(data, dict):
        raise OntologyError(f"{path}: method refs must be an object")
    refs = {}
    for name, ref in data.items():
        ok = (isinstance(ref, dict) and set(ref) <= {"title", "year", "url"}
              and isinstance(ref.get("title"), str) and ref["title"].strip()
              and isinstance(ref.get("year"), int) and not isinstance(ref.get("year"), bool)
              and isinstance(ref.get("url", ""), str))
        if not ok:
            raise OntologyError(f"method ref {name!r} needs a 'title' string, an int 'year', and an optional 'url'")
        refs[name] = dict(ref)
    return refs


def write_ontology(out_dir: Path | str, ontology: dict) -> Path:
    """Write the site copy of the (validated) ontology to ``<out_dir>/ontology.json``."""
    out_path = Path(out_dir) / ONTOLOGY_FILENAME
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(ontology, ensure_ascii=False), encoding="utf-8")
    return out_path
