#!/usr/bin/env python3
"""Report dataset scale metrics for resume/README."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report dataset stats.")
    parser.add_argument(
        "--processed-dir",
        type=Path,
        required=True,
        help="Directory containing ratings.parquet and movies.parquet.",
    )
    parser.add_argument(
        "--features-dir",
        type=Path,
        default=None,
        help="Optional directory containing movie_features.parquet and user_features.parquet.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional JSON output path.",
    )
    return parser.parse_args()


def load_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing expected file: {path}")
    return pd.read_parquet(path)


def main() -> None:
    args = parse_args()

    ratings = load_parquet(args.processed_dir / "ratings.parquet")
    movies = load_parquet(args.processed_dir / "movies.parquet")

    users = None
    movie_features = None
    if args.features_dir:
        user_path = args.features_dir / "user_features.parquet"
        movie_path = args.features_dir / "movie_features.parquet"
        if user_path.exists():
            users = pd.read_parquet(user_path)
        if movie_path.exists():
            movie_features = pd.read_parquet(movie_path)

    per_user = ratings.groupby("userId").size()
    per_movie = ratings.groupby("movieId").size()

    metrics = {
        "ratings_rows": int(len(ratings)),
        "unique_users": int(ratings["userId"].nunique()),
        "unique_movies_rated": int(ratings["movieId"].nunique()),
        "movies_catalog_size": int(len(movies)),
        "ratings_per_user_mean": float(per_user.mean()),
        "ratings_per_user_median": float(per_user.median()),
        "ratings_per_user_p95": float(np.percentile(per_user, 95)),
        "ratings_per_movie_mean": float(per_movie.mean()),
        "ratings_per_movie_median": float(per_movie.median()),
        "ratings_per_movie_p95": float(np.percentile(per_movie, 95)),
    }

    if users is not None:
        metrics["user_feature_rows"] = int(len(users))
    if movie_features is not None:
        metrics["movie_feature_rows"] = int(len(movie_features))

    print(json.dumps(metrics, indent=2))

    if args.out:
        args.out.write_text(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
