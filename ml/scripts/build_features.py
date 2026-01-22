#!/usr/bin/env python3
"""Build basic user/movie feature tables from MovieLens ratings."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build MovieLens feature tables.")
    parser.add_argument(
        "--processed-dir",
        type=Path,
        required=True,
        help="Directory containing Parquet outputs (ratings, movies, links).",
    )
    parser.add_argument(
        "--tmdb-csv",
        type=Path,
        default=None,
        help="Optional TMDB enrichment CSV to join into movie features.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="Output directory for feature tables.",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional cap for ratings rows (debugging).",
    )
    return parser.parse_args()


def load_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing expected file: {path}")
    return pd.read_parquet(path)


def ensure_out_dir(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)


def build_movie_features(ratings: pd.DataFrame, movies: pd.DataFrame) -> pd.DataFrame:
    movie_agg = (
        ratings.groupby("movieId")["rating"]
        .agg(["count", "mean", "std"])
        .rename(
            columns={
                "count": "rating_count",
                "mean": "rating_mean",
                "std": "rating_std",
            }
        )
        .reset_index()
    )

    last_ts = (
        ratings.groupby("movieId")["timestamp"].max().rename("last_rating_ts").reset_index()
    )

    out = movies.merge(movie_agg, on="movieId", how="left").merge(
        last_ts, on="movieId", how="left"
    )
    return out


def build_user_features(ratings: pd.DataFrame) -> pd.DataFrame:
    user_agg = (
        ratings.groupby("userId")["rating"]
        .agg(["count", "mean", "std"])
        .rename(
            columns={
                "count": "rating_count",
                "mean": "rating_mean",
                "std": "rating_std",
            }
        )
        .reset_index()
    )

    last_ts = (
        ratings.groupby("userId")["timestamp"].max().rename("last_rating_ts").reset_index()
    )

    out = user_agg.merge(last_ts, on="userId", how="left")
    return out


def maybe_join_tmdb(movie_features: pd.DataFrame, tmdb_csv: Optional[Path]) -> pd.DataFrame:
    if not tmdb_csv:
        return movie_features
    if not tmdb_csv.exists():
        raise FileNotFoundError(f"TMDB CSV not found: {tmdb_csv}")

    tmdb = pd.read_csv(tmdb_csv)
    join_cols = ["movieId", "tmdbId", "tmdb_found", "tmdb_release_date", "tmdb_runtime",
                 "tmdb_vote_avg", "tmdb_vote_count", "tmdb_popularity", "tmdb_genres",
                 "tmdb_poster_path", "tmdb_overview"]
    existing_cols = [c for c in join_cols if c in tmdb.columns]
    tmdb = tmdb[existing_cols]
    return movie_features.merge(tmdb, on="movieId", how="left")


def main() -> None:
    args = parse_args()

    ratings = load_parquet(args.processed_dir / "ratings.parquet")
    movies = load_parquet(args.processed_dir / "movies.parquet")

    if args.max_rows:
        ratings = ratings.head(args.max_rows)

    ensure_out_dir(args.out_dir)

    print("Building movie features...")
    movie_features = build_movie_features(ratings, movies)
    movie_features = maybe_join_tmdb(movie_features, args.tmdb_csv)
    movie_out = args.out_dir / "movie_features.parquet"
    movie_features.to_parquet(movie_out, index=False)

    print("Building user features...")
    user_features = build_user_features(ratings)
    user_out = args.out_dir / "user_features.parquet"
    user_features.to_parquet(user_out, index=False)

    print("Done.")
    print(f"  {movie_out}")
    print(f"  {user_out}")


if __name__ == "__main__":
    main()
