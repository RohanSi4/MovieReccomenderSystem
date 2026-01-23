#!/usr/bin/env python3
"""Compare heuristic vs LightGBM model ranking quality on validation data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

import lightgbm as lgb
import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare heuristic vs model NDCG.")
    parser.add_argument(
        "--training-dir",
        type=Path,
        required=True,
        help="Directory containing val.parquet.",
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        required=True,
        help="Directory containing lightgbm_model.txt and feature_columns.json.",
    )
    parser.add_argument(
        "--ndcg-k",
        type=int,
        default=10,
        help="k for NDCG@k evaluation.",
    )
    parser.add_argument(
        "--max-per-user",
        type=int,
        default=5000,
        help="Cap interactions per user to avoid huge groups.",
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


def cap_per_user(df: pd.DataFrame, max_per_user: int) -> pd.DataFrame:
    if max_per_user <= 0:
        return df
    if "timestamp" in df.columns:
        df = df.sort_values(["userId", "timestamp"])
    return df.groupby("userId", as_index=False).tail(max_per_user)


def prepare_labels(df: pd.DataFrame) -> pd.Series:
    return (df["label"] * 2).round().astype(int)


def ndcg_at_k(df: pd.DataFrame, scores: np.ndarray, k: int) -> float:
    work = df[["userId", "label_int"]].copy()
    work["score"] = scores

    ndcgs: List[float] = []
    for _, group in work.groupby("userId"):
        if len(group) < 2:
            continue
        top_pred = group.sort_values("score", ascending=False).head(k)
        top_true = group.sort_values("label_int", ascending=False).head(k)

        gains_pred = (2 ** top_pred["label_int"].to_numpy() - 1)
        gains_true = (2 ** top_true["label_int"].to_numpy() - 1)

        discounts = 1.0 / np.log2(np.arange(2, len(gains_pred) + 2))
        dcg = np.sum(gains_pred * discounts)
        idcg = np.sum(gains_true * discounts)
        if idcg > 0:
            ndcgs.append(dcg / idcg)

    return float(np.mean(ndcgs)) if ndcgs else 0.0


def get_column(df: pd.DataFrame, name: str, fallback: str | None = None) -> pd.Series:
    if name in df.columns:
        return df[name]
    if fallback and fallback in df.columns:
        return df[fallback]
    return pd.Series(0.0, index=df.index)


def heuristic_scores(df: pd.DataFrame) -> np.ndarray:
    rating_mean = get_column(df, "rating_mean_movie", "rating_mean").fillna(0.0)
    rating_count = get_column(df, "rating_count_movie", "rating_count").fillna(0).astype(float)
    tmdb_vote = get_column(df, "tmdb_vote_avg").fillna(0.0)
    tmdb_pop = get_column(df, "tmdb_popularity").fillna(0.0)
    user_mean = get_column(df, "rating_mean_user", "rating_mean").fillna(0.0)

    score = rating_mean
    score = score + 0.15 * tmdb_vote
    score = score + 0.02 * tmdb_pop
    score = score + 0.5 * np.log1p(rating_count)

    # user preference adjustment
    score = score + 1.0 * user_mean
    score = score - 1.0 * (rating_mean - user_mean).abs()

    return score.to_numpy()


def model_scores(df: pd.DataFrame, model_dir: Path) -> np.ndarray:
    model_path = model_dir / "lightgbm_model.txt"
    features_path = model_dir / "feature_columns.json"

    if not model_path.exists():
        raise FileNotFoundError(f"Missing model file: {model_path}")
    if not features_path.exists():
        raise FileNotFoundError(f"Missing feature list: {features_path}")

    feature_cols = json.loads(features_path.read_text())

    model = lgb.Booster(model_file=str(model_path))
    X = df.reindex(columns=feature_cols, fill_value=0).fillna(0)
    return model.predict(X)


def main() -> None:
    args = parse_args()

    val = load_parquet(args.training_dir / "val.parquet")
    val = cap_per_user(val, args.max_per_user)
    val = val.copy()
    val["label_int"] = prepare_labels(val)

    heuristic_pred = heuristic_scores(val)
    heuristic_ndcg = ndcg_at_k(val, heuristic_pred, args.ndcg_k)

    model_pred = model_scores(val, args.model_dir)
    model_ndcg = ndcg_at_k(val, model_pred, args.ndcg_k)

    improvement = 0.0
    if heuristic_ndcg > 0:
        improvement = (model_ndcg - heuristic_ndcg) / heuristic_ndcg

    metrics = {
        f"ndcg@{args.ndcg_k}_heuristic": heuristic_ndcg,
        f"ndcg@{args.ndcg_k}_model": model_ndcg,
        "ndcg_improvement_pct": improvement * 100.0,
        "rows_evaluated": len(val),
        "users_evaluated": int(val["userId"].nunique()),
    }

    print(json.dumps(metrics, indent=2))

    if args.out:
        args.out.write_text(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
