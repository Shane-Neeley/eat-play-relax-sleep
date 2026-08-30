#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "google-api-python-client>=2.170.0",
#   "google-auth-httplib2>=0.2.0",
#   "google-auth-oauthlib>=1.2.2",
# ]
# ///
"""Read a compact, channel-owner YouTube Analytics report.

This is deliberately read-only. It never starts OAuth, changes metadata, or
uploads anything. If the token lacks the Analytics scope, it exits with the
one-time re-authentication action instead of guessing from public view counts.
"""

from __future__ import annotations

import argparse
from datetime import date
import json
import os
from pathlib import Path
from typing import Any


ANALYTICS_SCOPE = "https://www.googleapis.com/auth/yt-analytics.readonly"
DEFAULT_TOKEN = Path("~/.config/youtube-channel/token.json").expanduser()
SUMMARY_METRICS = "views,engagedViews,estimatedMinutesWatched,subscribersGained"
VIDEO_METRICS = (
    "views,engagedViews,estimatedMinutesWatched,averageViewDuration,"
    "averageViewPercentage,subscribersGained"
)
RETENTION_DIMENSION = "elapsedVideoTimeRatio"
RETENTION_METRICS = (
    "audienceWatchRatio,relativeRetentionPerformance,startedWatching,"
    "stoppedWatching,totalSegmentImpressions"
)
MAX_RETENTION_VIDEOS = 10


def _iso_date(value: str) -> str:
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use YYYY-MM-DD") from exc
    return value


def query_parameters(
    start_date: str,
    end_date: str,
    metrics: str,
    *,
    dimensions: str | None = None,
    sort: str | None = None,
    max_results: int | None = None,
) -> dict[str, Any]:
    """Build a reports.query payload without contacting Google."""
    payload: dict[str, Any] = {
        "ids": "channel==MINE",
        "startDate": start_date,
        "endDate": end_date,
        "metrics": metrics,
    }
    if dimensions:
        payload["dimensions"] = dimensions
    if sort:
        payload["sort"] = sort
    if max_results is not None:
        payload["maxResults"] = max_results
    return payload


def retention_query_parameters(
    start_date: str,
    end_date: str,
    video_id: str,
) -> dict[str, Any]:
    """Build a single-video audience-retention query without contacting Google."""
    if not video_id or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for character in video_id):
        raise ValueError("video_id must contain only YouTube ID characters")
    payload = query_parameters(
        start_date,
        end_date,
        RETENTION_METRICS,
        dimensions=RETENTION_DIMENSION,
    )
    payload["filters"] = f"video=={video_id}"
    return payload


def _load_credentials(token_path: Path):
    """Load an existing token, refusing to silently re-authorize it."""
    try:
        from google.oauth2.credentials import Credentials
    except ImportError as exc:  # pragma: no cover - exercised by uv, not unit tests
        raise SystemExit("Install the script dependencies with uv run scripts/youtube_analytics_report.py") from exc

    if not token_path.is_file():
        raise SystemExit(f"YouTube token not found: {token_path}. Run the approved YouTube auth flow once.")
    try:
        token_record = json.loads(token_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Could not read YouTube token: {token_path}") from exc
    scopes = set(token_record.get("scopes") or [])
    if ANALYTICS_SCOPE not in scopes:
        raise SystemExit(
            "YouTube token lacks read-only Analytics scope. Re-run the approved "
            "YouTube channel auth flow once, then rerun this read-only report."
        )
    credentials = Credentials.from_authorized_user_file(str(token_path), [ANALYTICS_SCOPE])
    if credentials.expired and credentials.refresh_token:
        from google.auth.transport.requests import Request

        credentials.refresh(Request())
    if not credentials.valid:
        raise SystemExit("YouTube token is not valid; re-run the approved YouTube auth flow once.")
    return credentials


def run_report(
    start_date: str,
    end_date: str,
    token_path: Path,
    *,
    retention_videos: list[str] | None = None,
) -> dict[str, Any]:
    """Fetch summary, per-video rows, and optional single-video retention rows."""
    try:
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
    except ImportError as exc:  # pragma: no cover - exercised by uv, not unit tests
        raise SystemExit("Install the script dependencies with uv run scripts/youtube_analytics_report.py") from exc

    credentials = _load_credentials(token_path)
    service = build("youtubeAnalytics", "v2", credentials=credentials, cache_discovery=False)
    summary_query = query_parameters(start_date, end_date, SUMMARY_METRICS)
    video_query = query_parameters(
        start_date,
        end_date,
        VIDEO_METRICS,
        dimensions="video",
        sort="-views",
        max_results=50,
    )
    try:
        summary = service.reports().query(**summary_query).execute()
        videos = service.reports().query(**video_query).execute()
        retention = {
            video_id: service.reports()
            .query(**retention_query_parameters(start_date, end_date, video_id))
            .execute()
            for video_id in (retention_videos or [])
        }
    except HttpError as exc:
        detail = exc.content.decode("utf-8", errors="replace") if exc.content else str(exc)
        raise SystemExit(f"YouTube Analytics API error {exc.resp.status}: {detail}") from exc
    return {
        "schema": "eprs.youtube-analytics-report/v1",
        "channel": "MINE",
        "start_date": start_date,
        "end_date": end_date,
        "summary": summary,
        "videos": videos,
        "retention": retention,
    }


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--start-date", required=True, type=_iso_date)
    command.add_argument("--end-date", required=True, type=_iso_date)
    command.add_argument("--token", default=os.getenv("YOUTUBE_TOKEN", str(DEFAULT_TOKEN)))
    command.add_argument(
        "--retention-video",
        action="append",
        default=[],
        metavar="VIDEO_ID",
        help=f"include audience retention for one video; repeat up to {MAX_RETENTION_VIDEOS} times",
    )
    return command


def main() -> None:
    args = parser().parse_args()
    if args.start_date > args.end_date:
        raise SystemExit("--start-date must be on or before --end-date")
    if len(args.retention_video) > MAX_RETENTION_VIDEOS:
        raise SystemExit(f"--retention-video may be repeated at most {MAX_RETENTION_VIDEOS} times")
    try:
        report = run_report(
            args.start_date,
            args.end_date,
            Path(args.token).expanduser(),
            retention_videos=args.retention_video,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
