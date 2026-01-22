#!/usr/bin/env python3
"""Validate processed MovieLens data with basic integrity checks."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate MovieLens Parquet outputs.")
    parser.add_argument(
        "--processed-dir",
        type=Path,
        required=True,
        help="Directory containing Parquet files from ingestion.",
    )
    return parser.parse_args()


def load_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing expected file: {path}")
    return pd.read_parquet(path)


def summarize_counts(ratings: pd.DataFrame, movies: pd.DataFrame) -> None:
    print("\n[counts]")
    print(f"  ratings rows: {len(ratings):,}")
    print(f"  movies rows: {len(movies):,}")
    print(f"  unique users: {ratings['userId'].nunique():,}")
    print(f"  unique rated movies: {ratings['movieId'].nunique():,}")


def summarize_ranges(ratings: pd.DataFrame) -> None:
    print("\n[ranges]")
    print(f"  rating min/max: {ratings['rating'].min()} / {ratings['rating'].max()}")
    ts = pd.to_datetime(ratings["timestamp"], unit="s", errors="coerce")
    print(f"  timestamp min/max: {ts.min()} / {ts.max()}")


def summarize_nulls(links: pd.DataFrame, tags: pd.DataFrame) -> None:
    print("\n[nulls]")
    print(f"  links tmdbId nulls: {links['tmdbId'].isna().sum():,}")
    print(f"  tags nulls: {tags['tag'].isna().sum():,}")


def summarize_coverage(ratings: pd.DataFrame, movies: pd.DataFrame, links: pd.DataFrame) -> None:
    print("\n[coverage]")
    ratings_movies = ratings.merge(movies[["movieId"]], on="movieId", how="left", indicator=True)
    missing_movies = (ratings_movies["_merge"] == "left_only").sum()
    print(f"  ratings missing movies: {missing_movies:,}")

    movies_links = movies.merge(links[["movieId"]], on="movieId", how="left", indicator=True)
    missing_links = (movies_links["_merge"] == "left_only").sum()
    print(f"  movies missing links: {missing_links:,}")


def main() -> None:
    args = parse_args()
    processed_dir: Path = args.processed_dir

    ratings = load_parquet(processed_dir / "ratings.parquet")
    movies = load_parquet(processed_dir / "movies.parquet")
    tags = load_parquet(processed_dir / "tags.parquet")
    links = load_parquet(processed_dir / "links.parquet")

    summarize_counts(ratings, movies)
    summarize_ranges(ratings)
    summarize_nulls(links, tags)
    summarize_coverage(ratings, movies, links)


if __name__ == "__main__":
    main()
