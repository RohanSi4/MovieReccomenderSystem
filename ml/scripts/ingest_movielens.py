#!/usr/bin/env python3
"""Ingest MovieLens CSVs into normalized Parquet files with basic validation."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Tuple

import pandas as pd


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    filename: str
    required_cols: Tuple[str, ...]


SPECS = (
    DatasetSpec(
        name="ratings",
        filename="ratings.csv",
        required_cols=("userId", "movieId", "rating", "timestamp"),
    ),
    DatasetSpec(
        name="movies",
        filename="movies.csv",
        required_cols=("movieId", "title", "genres"),
    ),
    DatasetSpec(
        name="tags",
        filename="tags.csv",
        required_cols=("userId", "movieId", "tag", "timestamp"),
    ),
    DatasetSpec(
        name="links",
        filename="links.csv",
        required_cols=("movieId", "imdbId", "tmdbId"),
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest MovieLens CSVs.")
    parser.add_argument(
        "--raw-dir",
        type=Path,
        required=True,
        help="Directory containing MovieLens CSV files.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="Output directory for Parquet files.",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional cap for rows loaded per file (debugging).",
    )
    return parser.parse_args()


def load_csv(path: Path, required_cols: Iterable[str], max_rows: int | None) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing expected file: {path}")

    df = pd.read_csv(path, nrows=max_rows)
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"{path.name} missing columns: {missing}")
    return df


def print_summary(name: str, df: pd.DataFrame) -> None:
    print(f"\n[{name}] rows={len(df):,} cols={len(df.columns)}")
    if name == "ratings":
        rating_min = df["rating"].min()
        rating_max = df["rating"].max()
        ts_min = pd.to_datetime(df["timestamp"], unit="s", errors="coerce").min()
        ts_max = pd.to_datetime(df["timestamp"], unit="s", errors="coerce").max()
        print(f"  rating range: {rating_min} - {rating_max}")
        print(f"  timestamp range: {ts_min} - {ts_max}")
    if name == "movies":
        print(f"  unique movies: {df['movieId'].nunique():,}")
    if name == "tags":
        print(f"  unique tags: {df['tag'].nunique():,}")
    if name == "links":
        print(f"  tmdbId nulls: {df['tmdbId'].isna().sum():,}")


def ensure_out_dir(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)


def write_parquet(out_dir: Path, name: str, df: pd.DataFrame) -> None:
    out_path = out_dir / f"{name}.parquet"
    try:
        df.to_parquet(out_path, index=False)
    except Exception as exc:  # pragma: no cover - dependency-specific
        raise RuntimeError(
            "Failed to write Parquet. Install pyarrow or fastparquet."
        ) from exc


def main() -> None:
    args = parse_args()
    raw_dir: Path = args.raw_dir
    out_dir: Path = args.out_dir

    ensure_out_dir(out_dir)

    datasets: Dict[str, pd.DataFrame] = {}
    for spec in SPECS:
        df = load_csv(raw_dir / spec.filename, spec.required_cols, args.max_rows)
        datasets[spec.name] = df
        print_summary(spec.name, df)
        write_parquet(out_dir, spec.name, df)

    print("\nDone. Parquet files written to:", out_dir)


if __name__ == "__main__":
    main()
