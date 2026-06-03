import argparse
import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd

from src.paths import PROCESSED_DIR, ensure_directories
from src.utils.io import read_csv, write_csv
from src.utils.logging_utils import get_logger


GITHUB_API = "https://api.github.com/repos/{repo_name}"


def request_json(url: str, token: str | None, timeout: int = 30) -> tuple[int, dict[str, str], dict[str, Any] | None]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ai-knowledge-commons-shock-research",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
            return response.status, dict(response.headers), body
    except HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
        except Exception:
            body = {"message": str(exc)}
        return exc.code, dict(exc.headers), body
    except URLError as exc:
        return 0, {}, {"message": str(exc)}


def normalize_repo_response(repo_name: str, rank: int, status: int, headers: dict[str, str], body: dict[str, Any] | None) -> dict[str, Any]:
    body = body or {}
    return {
        "rank": rank,
        "repo_name": repo_name,
        "http_status": status,
        "api_message": body.get("message"),
        "github_id": body.get("id"),
        "full_name": body.get("full_name"),
        "private": body.get("private"),
        "archived": body.get("archived"),
        "disabled": body.get("disabled"),
        "fork": body.get("fork"),
        "primary_language": body.get("language"),
        "stargazers_count": body.get("stargazers_count"),
        "forks_count": body.get("forks_count"),
        "open_issues_count": body.get("open_issues_count"),
        "created_at": body.get("created_at"),
        "updated_at": body.get("updated_at"),
        "pushed_at": body.get("pushed_at"),
        "owner_login": (body.get("owner") or {}).get("login"),
        "owner_type": (body.get("owner") or {}).get("type"),
        "rate_limit_remaining": headers.get("x-ratelimit-remaining"),
        "rate_limit_reset": headers.get("x-ratelimit-reset"),
    }


def fetch_metadata(input_path: Path, output_path: Path, top_n: int, sleep_seconds: float, resume: bool) -> pd.DataFrame:
    logger = get_logger(__name__)
    top_repos = read_csv(input_path).head(top_n).copy()
    token = os.getenv("GITHUB_TOKEN")

    existing = pd.DataFrame()
    done: set[str] = set()
    if resume and output_path.exists():
        existing = read_csv(output_path)
        done = set(existing["repo_name"].dropna().astype(str))
        logger.info("Resuming with %s existing repo metadata rows", len(done))

    rows: list[dict[str, Any]] = []
    for rank, repo_name in enumerate(top_repos["repo_name"].astype(str), start=1):
        if repo_name in done:
            continue
        url = GITHUB_API.format(repo_name=repo_name)
        status, headers, body = request_json(url, token=token)
        row = normalize_repo_response(repo_name, rank, status, headers, body)
        rows.append(row)
        remaining = row.get("rate_limit_remaining")
        logger.info("Fetched %s | status=%s | language=%s | remaining=%s", repo_name, status, row["primary_language"], remaining)

        if remaining is not None:
            try:
                if int(remaining) <= 1:
                    logger.warning("GitHub API rate limit nearly exhausted; stopping early.")
                    break
            except ValueError:
                pass
        if sleep_seconds:
            time.sleep(sleep_seconds)

    new = pd.DataFrame(rows)
    out = pd.concat([existing, new], ignore_index=True)
    if not out.empty:
        out = out.drop_duplicates(subset=["repo_name"], keep="last")
        out = out.sort_values("rank")
    write_csv(out, output_path)
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch public GitHub repository metadata for sampled GH Archive top repos.")
    parser.add_argument("--input", type=Path, default=PROCESSED_DIR / "gharchive" / "top_repos_sample_2021_2024.csv")
    parser.add_argument("--output", type=Path, default=PROCESSED_DIR / "gharchive" / "top_repos_github_metadata.csv")
    parser.add_argument("--top-n", type=int, default=50)
    parser.add_argument("--sleep-seconds", type=float, default=0.2)
    parser.add_argument("--no-resume", action="store_true")
    return parser.parse_args()


def main() -> None:
    ensure_directories()
    args = parse_args()
    out = fetch_metadata(args.input, args.output, args.top_n, args.sleep_seconds, resume=not args.no_resume)
    logger = get_logger(__name__)
    logger.info("Wrote %s rows to %s", len(out), args.output)
    if not out.empty:
        logger.info("\n%s", out.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
