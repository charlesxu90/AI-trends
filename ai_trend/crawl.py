"""Config-driven OpenReview crawl wrapper around the existing Scrapy spider.

The original workflow hand-edits ``data/scrapy_crawl/run_scrapy_<year>.sh``. This
makes the crawl declarative: jobs live in ``config/crawl.json`` and this runner
builds + executes the ``scrapy crawl`` command for each, writing JSON the
``ingest`` step then merges.

IMPORTANT: OpenReview ``venue`` / ``domain`` strings are API-specific and change
per cycle; they must be verified/updated for new conferences. This wrapper does
not invent them. CVPR / ICCV are not on OpenReview and are out of scope here.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

# Conference tokens become path segments; constrain them to a safe charset so a
# config value can never escape the output directory.
_SAFE_TOKEN = re.compile(r"^[a-z0-9_-]{1,32}$")

DEFAULT_SPIDER = "scrapy_openreview2"
DEFAULT_SCRAPY_DIR = Path(__file__).resolve().parent.parent / "data" / "scrapy_crawl"
DEFAULT_RAW_DIR = DEFAULT_SCRAPY_DIR  # spider output lives under data/scrapy_crawl/<year>/
DEFAULT_LIMIT = 1000


@dataclass
class CrawlJob:
    year: int
    source: str
    token: str
    type: str
    venue: str
    domain: str | None = None
    offset: int = 0
    limit: int = DEFAULT_LIMIT

    def output_name(self) -> str:
        # e.g. iclr2025-poster-1000.json ; ingest globs "<token><year>*.json"
        return f"{self.token}{self.year}-{self.type}-{self.offset}.json"


@dataclass
class CrawlResult:
    job: CrawlJob
    ok: bool
    output: Path
    message: str = ""


def load_jobs(config_path: Path | str) -> tuple[str, str, list[CrawlJob]]:
    """Return ``(spider, details, jobs)`` from a crawl config file."""
    data = json.loads(Path(config_path).read_text(encoding="utf-8"))
    spider = data.get("spider", DEFAULT_SPIDER)
    details = data.get("details", "replyCount")
    jobs = []
    for j in data.get("jobs", []):
        token = str(j["token"]).lower()
        job_type = str(j["type"])
        for field, value in (("token", token), ("type", job_type)):
            if not _SAFE_TOKEN.match(value):  # both become path segments in the filename
                raise ValueError(f"unsafe crawl {field}: {value!r}")
        jobs.append(
            CrawlJob(
                year=int(j["year"]),
                source=j["source"],
                token=token,
                type=job_type,
                venue=j["venue"],
                domain=j.get("domain"),
                offset=int(j.get("offset", 0)),
                limit=int(j.get("limit", DEFAULT_LIMIT)),
            )
        )
    return spider, details, jobs


def build_command(
    job: CrawlJob, raw_dir: Path | str, *, spider: str = DEFAULT_SPIDER, details: str = "replyCount"
) -> list[str]:
    """Build the ``scrapy crawl`` argv for one job (output path relative to raw_dir)."""
    out = Path(raw_dir) / str(job.year) / job.output_name()
    cmd = [
        "scrapy", "crawl", spider,
        "-o", str(out),
        "-a", f"year={job.year}",
        "-a", f"source={job.source}",
        "-a", f"type={job.type}",
        "-a", f"venue={job.venue}",
        "-a", f"details={details}",
        "-a", f"offset={job.offset}",
        "-a", f"limit={job.limit}",
    ]
    if job.domain:
        cmd += ["-a", f"domain={job.domain}"]
    cmd.append("--nolog")
    return cmd


def crawl(
    jobs: list[CrawlJob],
    *,
    raw_dir: Path | str = DEFAULT_RAW_DIR,
    scrapy_dir: Path | str = DEFAULT_SCRAPY_DIR,
    spider: str = DEFAULT_SPIDER,
    details: str = "replyCount",
    dry_run: bool = False,
) -> list[CrawlResult]:
    """Run each crawl job best-effort; a failed job never aborts the rest."""
    raw_dir = Path(raw_dir)
    raw_root = raw_dir.resolve()
    results: list[CrawlResult] = []
    for job in jobs:
        out = (raw_dir / str(job.year) / job.output_name()).resolve()
        if not str(out).startswith(str(raw_root) + "/") and out != raw_root:
            results.append(CrawlResult(job, ok=False, output=out, message="output path escapes raw_dir"))
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        cmd = build_command(job, raw_dir, spider=spider, details=details)
        if dry_run:
            results.append(CrawlResult(job, ok=True, output=out, message="dry-run: " + " ".join(cmd)))
            continue
        try:
            proc = subprocess.run(cmd, cwd=str(scrapy_dir), capture_output=True, text=True, timeout=600)
            ok = proc.returncode == 0 and out.exists()
            results.append(
                CrawlResult(job, ok=ok, output=out, message=(proc.stderr or "")[-500:] if not ok else "ok")
            )
        except (subprocess.SubprocessError, OSError) as exc:
            results.append(CrawlResult(job, ok=False, output=out, message=str(exc)))
    return results
