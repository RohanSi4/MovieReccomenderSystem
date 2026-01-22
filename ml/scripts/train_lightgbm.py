#!/usr/bin/env python3
"""Train a LightGBM ranker on MovieLens features."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Tuple

import lightgbm as lgb
import numpy as np
import pandas as pd


NON_FEATURE_COLS = {
    "label",
    "label_int",
    "userId",
    "movieId",
    "timestamp",
    "title",
    "genres",
    "ml_genres",
    "tmdb_title",
    "tmdb_release_date",
    "tmdb_genres",
    "tmdb_poster_path",
    "tmdb_overview",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train LightGBM ranker.")
    parser.add_argument(
        "--training-dir",
        type=Path,
        required=True,
        help="Directory containing train.parquet and val.parquet.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="Output directory for model artifacts.",
    )
    parser.add_argument(
        "--num-iterations",
        type=int,
        default=200,
        help="Number of boosting rounds.",
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=0.1,
        help="Learning rate.",
    )
    parser.add_argument(
        "--num-leaves",
        type=int,
        default=63,
        help="Number of leaves.",
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
        help="Cap interactions per user to avoid LightGBM query size limits.",
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


def prepare_dataset(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series, np.ndarray]:
    df = df.sort_values("userId")

    feature_cols = [
        c
        for c in df.columns
        if c not in NON_FEATURE_COLS and pd.api.types.is_numeric_dtype(df[c])
    ]
    if not feature_cols:
        raise ValueError("No numeric feature columns found.")

    X = df[feature_cols]
    y = df["label_int"].astype(int)
    group = df.groupby("userId").size().to_numpy()
    return X, y, group


def ndcg_at_k(
    df: pd.DataFrame, scores: np.ndarray, k: int, label_col: str = "label"
) -> float:
    work = df[["userId", label_col]].copy()
    work["score"] = scores

    ndcgs: List[float] = []
    for _, group in work.groupby("userId"):
        if len(group) < 2:
            continue
        top_pred = group.sort_values("score", ascending=False).head(k)
        top_true = group.sort_values(label_col, ascending=False).head(k)

        gains_pred = (2 ** top_pred[label_col].to_numpy() - 1)
        gains_true = (2 ** top_true[label_col].to_numpy() - 1)

        discounts = 1.0 / np.log2(np.arange(2, len(gains_pred) + 2))
        dcg = np.sum(gains_pred * discounts)
        idcg = np.sum(gains_true * discounts)
        if idcg > 0:
            ndcgs.append(dcg / idcg)

    return float(np.mean(ndcgs)) if ndcgs else 0.0


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def ensure_out_dir(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)


def main() -> None:
    args = parse_args()

    train = load_parquet(args.training_dir / "train.parquet")
    val = load_parquet(args.training_dir / "val.parquet")

    train = cap_per_user(train, args.max_per_user)
    val = cap_per_user(val, args.max_per_user)

    # Convert half-star ratings to integer labels for ranking
    train = train.copy()
    val = val.copy()
    train["label_int"] = (train["label"] * 2).round().astype(int)
    val["label_int"] = (val["label"] * 2).round().astype(int)

    X_train, y_train, group_train = prepare_dataset(train)
    X_val, y_val, group_val = prepare_dataset(val)

    max_label = int(max(y_train.max(), y_val.max()))
    params = {
        "objective": "lambdarank",
        "metric": "ndcg",
        "learning_rate": args.learning_rate,
        "num_leaves": args.num_leaves,
        "label_gain": list(range(max_label + 1)),
        "verbosity": -1,
    }

    train_set = lgb.Dataset(X_train, label=y_train, group=group_train)
    val_set = lgb.Dataset(X_val, label=y_val, group=group_val)

    model = lgb.train(
        params,
        train_set,
        num_boost_round=args.num_iterations,
        valid_sets=[val_set],
        valid_names=["val"],
    )

    val_pred = model.predict(X_val)
    metrics = {
        "rmse_label_int": rmse(y_val.to_numpy(), val_pred),
        f"ndcg@{args.ndcg_k}": ndcg_at_k(val.assign(label=y_val), val_pred, args.ndcg_k),
    }

    ensure_out_dir(args.out_dir)
    model_path = args.out_dir / "lightgbm_model.txt"
    features_path = args.out_dir / "feature_columns.json"
    metrics_path = args.out_dir / "metrics.json"

    model.save_model(model_path)
    features_path.write_text(json.dumps(list(X_train.columns), indent=2))
    metrics_path.write_text(json.dumps(metrics, indent=2))

    print("Training complete.")
    print(f"  Model: {model_path}")
    print(f"  Features: {features_path}")
    print(f"  Metrics: {metrics_path}")


if __name__ == "__main__":
    main()
