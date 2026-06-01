"""End-to-end CLI tests for assign and curate (no network, no model)."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from ai_trend.candidates import DEFAULT_MODEL_PATH
from ai_trend.cli import main


def _write_config(config_dir):
    (config_dir / "taxonomy.json").write_text(
        json.dumps({"graph": ["graph"], "llm": ["large language model"]}),
        encoding="utf-8",
    )
    (config_dir / "useless_keywords.json").write_text(
        json.dumps(["model"]), encoding="utf-8"
    )


def test_assign_writes_default_topics_path(tmp_path):
    # Arrange
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    _write_config(config_dir)
    csv = tmp_path / "5_iclr.csv"
    pd.DataFrame(
        {"title": ["A graph paper", "vision study"], "abstract": ["uses graph", "none"]}
    ).to_csv(csv, index=False)

    # Act
    rc = main(["--config", str(config_dir), "assign", str(csv)])

    # Assert
    assert rc == 0
    out = csv.with_name("5_iclr.csv_topics.csv")
    assert out.exists()
    result = pd.read_csv(out)
    assert list(result["topic"].fillna("")) == ["graph", ""]


def test_assign_missing_file_returns_2(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    _write_config(config_dir)
    rc = main(["--config", str(config_dir), "assign", str(tmp_path / "nope.csv")])
    assert rc == 2


def test_curate_applies_decision_to_config(tmp_path):
    # Arrange
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    _write_config(config_dir)
    decision = tmp_path / "decision.json"
    decision.write_text(
        json.dumps(
            {
                "decisions": [
                    {"keyword": "splatting", "action": "new", "topic": "splatting"},
                    {"keyword": "gnn", "action": "existing", "topic": "graph"},
                    {"keyword": "approach", "action": "noise"},
                    {"keyword": "mesh", "action": "other"},
                ]
            }
        ),
        encoding="utf-8",
    )

    # Act
    rc = main(["--config", str(config_dir), "curate", str(decision)])

    # Assert
    assert rc == 0
    taxonomy = json.loads((config_dir / "taxonomy.json").read_text())
    blocklist = json.loads((config_dir / "useless_keywords.json").read_text())
    ledger = json.loads((config_dir / "other_keywords.json").read_text())
    assert taxonomy["splatting"] == ["splatting"]
    assert "gnn" in taxonomy["graph"]
    assert "approach" in blocklist
    assert ledger == ["mesh"]


@pytest.mark.skipif(not DEFAULT_MODEL_PATH.exists(), reason="scispaCy model not present")
def test_candidates_writes_payload(tmp_path):
    # Arrange
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    _write_config(config_dir)
    # 'splatting' is unknown to the tiny taxonomy and repeats enough to survive threshold
    titles = [f"gaussian splatting method number {i}" for i in range(8)]
    csv = tmp_path / "papers.csv"
    pd.DataFrame({"title": titles, "abstract": [""] * len(titles)}).to_csv(csv, index=False)
    out = tmp_path / "payload.json"

    # Act
    rc = main(
        [
            "--config", str(config_dir),
            "candidates", str(csv),
            "-o", str(out),
            "--threshold", "3",
            "--conference", "iclr", "--year", "2025",
        ]
    )

    # Assert
    assert rc == 0
    payload = json.loads(out.read_text())
    assert payload["conference"] == "iclr"
    assert payload["existing_topics"] == ["graph", "llm"]
    # scispaCy decides the entity span; assert a splatting-related candidate surfaced
    assert payload["candidates"], "expected at least one candidate"
    assert any("splatting" in c["keyword"] for c in payload["candidates"])


def test_candidates_missing_file_returns_2(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    _write_config(config_dir)
    rc = main(["--config", str(config_dir), "candidates", str(tmp_path / "nope.csv")])
    assert rc == 2


def test_curate_dry_run_writes_nothing(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    _write_config(config_dir)
    before = (config_dir / "taxonomy.json").read_text()
    decision = tmp_path / "d.json"
    decision.write_text(
        json.dumps({"decisions": [{"keyword": "x", "action": "noise"}]}),
        encoding="utf-8",
    )
    rc = main(["--config", str(config_dir), "curate", "--dry-run", str(decision)])
    assert rc == 0
    assert (config_dir / "taxonomy.json").read_text() == before


def _setup_trend_data(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    _write_config(config_dir)
    data_dir = tmp_path / "data"
    (data_dir / "2024").mkdir(parents=True)
    (data_dir / "2025").mkdir(parents=True)
    pd.DataFrame({"topic": ["graph", "graph", "llm"]}).to_csv(
        data_dir / "2024" / "5_iclr.csv_topics.csv", index=False
    )
    pd.DataFrame({"topic": ["graph", "llm", "llm", "llm"]}).to_csv(
        data_dir / "2025" / "5_iclr.csv_topics.csv", index=False
    )
    return config_dir, data_dir


def test_trends_json_output(tmp_path):
    config_dir, data_dir = _setup_trend_data(tmp_path)
    out = tmp_path / "trends.json"
    rc = main(
        ["--config", str(config_dir), "trends", "--data-dir", str(data_dir),
         "--min-count", "1", "-o", str(out)]
    )
    assert rc == 0
    payload = json.loads(out.read_text())
    iclr2025 = [t for t in payload if t["year"] == 2025][0]
    assert iclr2025["conference"] == "ICLR"
    assert iclr2025["previous_year"] == 2024
    assert iclr2025["top"][0] in {"graph", "llm"}
    assert "llm" in iclr2025["emerging"]  # llm grew 1->3


def test_trends_markdown_output(tmp_path):
    config_dir, data_dir = _setup_trend_data(tmp_path)
    rc = main(
        ["--config", str(config_dir), "trends", "--data-dir", str(data_dir), "--format", "markdown"]
    )
    assert rc == 0


def test_trends_missing_data_dir_returns_2(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    _write_config(config_dir)
    rc = main(["--config", str(config_dir), "trends", "--data-dir", str(tmp_path / "nope")])
    assert rc == 2
