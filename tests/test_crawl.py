"""Tests for the config-driven crawl wrapper (command construction + dry run)."""

from __future__ import annotations

import json

import pytest

from ai_trend.crawl import CrawlJob, build_command, crawl, load_jobs


def test_build_command_includes_all_args(tmp_path):
    job = CrawlJob(year=2025, source="ICLR", token="iclr", type="poster",
                   venue="ICLR%202025%20Poster", domain="ICLR.cc%2F2025%2FConference", offset=1000)
    cmd = build_command(job, tmp_path, spider="scrapy_openreview2")
    joined = " ".join(cmd)
    assert "scrapy crawl scrapy_openreview2" in joined
    assert "year=2025" in joined and "venue=ICLR%202025%20Poster" in joined
    assert "offset=1000" in joined and "domain=ICLR.cc%2F2025%2FConference" in joined
    assert cmd[cmd.index("-o") + 1].endswith("2025/iclr2025-poster-1000.json")


def test_build_command_omits_domain_when_absent(tmp_path):
    job = CrawlJob(year=2024, source="ICML", token="icml", type="oral", venue="V")
    assert "domain=" not in " ".join(build_command(job, tmp_path))


def test_load_jobs(tmp_path):
    cfg = tmp_path / "crawl.json"
    cfg.write_text(json.dumps({
        "spider": "s", "details": "replyCount",
        "jobs": [{"year": 2025, "source": "ICLR", "token": "iclr", "type": "oral", "venue": "V"}],
    }), encoding="utf-8")
    spider, details, jobs = load_jobs(cfg)
    assert spider == "s" and len(jobs) == 1 and jobs[0].year == 2025


def test_crawl_dry_run_runs_nothing(tmp_path):
    jobs = [CrawlJob(year=2025, source="ICLR", token="iclr", type="oral", venue="V")]
    results = crawl(jobs, raw_dir=tmp_path, dry_run=True)
    assert len(results) == 1 and results[0].ok
    assert results[0].message.startswith("dry-run:")


def test_load_jobs_rejects_unsafe_token(tmp_path):
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({"jobs": [
        {"year": 2025, "source": "X", "token": "../evil", "type": "oral", "venue": "V"}]}),
        encoding="utf-8")
    with pytest.raises(ValueError):
        load_jobs(cfg)


def test_crawl_blocks_path_escape(tmp_path):
    # defense-in-depth: a directly-built job whose path climbs out of raw_dir is blocked
    job = CrawlJob(year=2025, source="X", token="../" * 12 + "tmp/evil", type="x", venue="V")
    results = crawl([job], raw_dir=tmp_path / "raw", dry_run=False)
    assert not results[0].ok and "escape" in results[0].message
