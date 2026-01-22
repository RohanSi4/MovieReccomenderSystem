#!/usr/bin/env python3
"""Build a training dataset for a simple ranking model."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Tuple

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build training dataset from features + ratings.")
    parser.add_argument(
        "--processed-dir",
        type=Path,
        required=True,
        help="Directory containing ratings.parquet.",
    )
    parser.add_argument(
        "--features-dir",
        type=Path,
        required=True,
        help="Directory containing movie_features.parquet and user_features.parquet.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="Output directory for train/val datasets.",
    )
    parser.add_argument(
        "--val-fraction",
        type=float,
        default=0.1,
        help="Fraction of most-recent ratings to use for validation.",
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


def train_val_split(ratings: pd.DataFrame, val_fraction: float) -> Tuple[pd.DataFrame, pd.DataFrame]:
    ratings_sorted = ratings.sort_values("timestamp")
    split_idx = int(len(ratings_sorted) * (1.0 - val_fraction))
    train = ratings_sorted.iloc[:split_idx]
    val = ratings_sorted.iloc[split_idx:]
    return train, val


def build_dataset(
    ratings: pd.DataFrame, user_features: pd.DataFrame, movie_features: pd.DataFrame
) -> pd.DataFrame:
    base = ratings.merge(user_features, on="userId", how="left").merge(
        movie_features, on="movieId", how="left", suffixes=("_user", "_movie")
    )
    base = base.rename(columns={"rating": "label"})
    return base


def main() -> None:
    args = parse_args()

    ratings = load_parquet(args.processed_dir / "ratings.parquet")
    user_features = load_parquet(args.features_dir / "user_features.parquet")
    movie_features = load_parquet(args.features_dir / "movie_features.parquet")

    if args.max_rows:
        ratings = ratings.head(args.max_rows)

    train_ratings, val_ratings = train_val_split(ratings, args.val_fraction)

    print("Building train dataset...")
    train = build_dataset(train_ratings, user_features, movie_features)
    print("Building val dataset...")
    val = build_dataset(val_ratings, user_features, movie_features)

    ensure_out_dir(args.out_dir)
    train_out = args.out_dir / "train.parquet"
    val_out = args.out_dir / "val.parquet"

    train.to_parquet(train_out, index=False)
    val.to_parquet(val_out, index=False)

    print("Done.")
    print(f"  {train_out}")
    print(f"  {val_out}")


if __name__ == "__main__":
    main()
