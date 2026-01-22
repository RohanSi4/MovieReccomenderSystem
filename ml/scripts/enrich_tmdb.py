#!/usr/bin/env python3
"""Enrich MovieLens movies with TMDB metadata."""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd
import requests

TMDB_BASE_URL = "https://api.themoviedb.org/3"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enrich MovieLens movies with TMDB metadata.")
    parser.add_argument(
        "--processed-dir",
        type=Path,
        required=True,
        help="Directory containing Parquet outputs (movies.parquet, links.parquet).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output CSV path.",
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=4.0,
        help="Max requests per second.",
    )
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=500,
        help="Write progress to CSV every N fetched movies.",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Disable resume if output CSV already exists.",
    )
    parser.add_argument(
        "--max-movies",
        type=int,
        default=None,
        help="Optional cap for number of movies to fetch (debugging).",
    )
    return parser.parse_args()


def require_api_key() -> str:
    api_key = os.getenv("TMDB_API_KEY")
    if not api_key:
        raise RuntimeError("TMDB_API_KEY not set in environment.")
    return api_key


def load_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing expected file: {path}")
    return pd.read_parquet(path)


def tmdb_get_movie(tmdb_id: int, api_key: str) -> Dict[str, Any]:
    url = f"{TMDB_BASE_URL}/movie/{tmdb_id}"
    params = {"api_key": api_key}
    resp = requests.get(url, params=params, timeout=15)
    if resp.status_code == 404:
        return {"_missing": True}
    resp.raise_for_status()
    return resp.json()


def extract_fields(payload: Dict[str, Any]) -> Dict[str, Any]:
    if payload.get("_missing"):
        return {"tmdb_found": False}

    genres = payload.get("genres") or []
    return {
        "tmdb_found": True,
        "tmdb_title": payload.get("title"),
        "tmdb_release_date": payload.get("release_date"),
        "tmdb_runtime": payload.get("runtime"),
        "tmdb_vote_avg": payload.get("vote_average"),
        "tmdb_vote_count": payload.get("vote_count"),
        "tmdb_popularity": payload.get("popularity"),
        "tmdb_genres": "|".join([g.get("name", "") for g in genres if g.get("name")]),
        "tmdb_poster_path": payload.get("poster_path"),
        "tmdb_overview": payload.get("overview"),
    }


def load_existing(out_path: Path) -> pd.DataFrame:
    if not out_path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(out_path)
    except Exception as exc:
        raise RuntimeError(f"Failed to read existing output: {out_path}") from exc


def write_checkpoint(out_path: Path, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    df = pd.DataFrame(rows)
    write_header = not out_path.exists()
    df.to_csv(out_path, mode="a", header=write_header, index=False)


def main() -> None:
    args = parse_args()
    api_key = require_api_key()

    movies = load_parquet(args.processed_dir / "movies.parquet")
    links = load_parquet(args.processed_dir / "links.parquet")

    merged = movies.merge(links, on="movieId", how="left")
    merged = merged.dropna(subset=["tmdbId"]).copy()
    merged["tmdbId"] = merged["tmdbId"].astype(int)

    if args.max_movies:
        merged = merged.head(args.max_movies)

    existing = pd.DataFrame()
    if not args.no_resume and args.out.exists():
        existing = load_existing(args.out)
    existing_tmdb_ids = set(existing.get("tmdbId", pd.Series(dtype=int)).dropna().astype(int))

    results: List[Dict[str, Any]] = []
    sleep_s = 1.0 / max(args.rate_limit, 0.1)

    to_fetch = merged[~merged["tmdbId"].isin(existing_tmdb_ids)]
    print(
        f"Fetching TMDB data for {len(to_fetch):,} movies "
        f"(skipping {len(existing_tmdb_ids):,} already fetched)..."
    )
    for _, row in to_fetch.iterrows():
        tmdb_id = int(row["tmdbId"])
        try:
            payload = tmdb_get_movie(tmdb_id, api_key)
            fields = extract_fields(payload)
        except requests.RequestException as exc:
            fields = {"tmdb_found": False, "tmdb_error": str(exc)}

        results.append(
            {
                "movieId": int(row["movieId"]),
                "tmdbId": tmdb_id,
                "title": row.get("title"),
                "ml_genres": row.get("genres"),
                **fields,
            }
        )

        if (len(results) % args.checkpoint_every) == 0:
            write_checkpoint(args.out, results)
            print(f"  fetched {len(results):,} (checkpointed)")
            results.clear()

        time.sleep(sleep_s)

    write_checkpoint(args.out, results)
    print(f"\nDone. Wrote: {args.out}")


if __name__ == "__main__":
    main()
