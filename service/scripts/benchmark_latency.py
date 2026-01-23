#!/usr/bin/env python3
"""Simple latency benchmark for /rank endpoint."""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark /rank latency.")
    parser.add_argument(
        "--base-url",
        type=str,
        default="http://localhost:8080",
        help="Base URL for the Go service.",
    )
    parser.add_argument(
        "--users-csv",
        type=Path,
        default=Path("service/data/user_features.csv"),
        help="Path to user_features.csv.",
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=100,
        help="Number of requests.",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=25,
        help="Top K per request.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.users_csv.exists():
        raise FileNotFoundError(f"Missing users CSV: {args.users_csv}")

    users = pd.read_csv(args.users_csv)
    user_ids = users["userId"].dropna().astype(int).tolist()

    if not user_ids:
        raise RuntimeError("No user ids found")

    timings = []
    for _ in range(args.requests):
        uid = random.choice(user_ids)
        payload = {"user_id": uid, "k": args.k}
        start = time.perf_counter()
        resp = requests.post(f"{args.base_url}/rank", json=payload, timeout=10)
        resp.raise_for_status()
        timings.append((time.perf_counter() - start) * 1000.0)

    timings = np.array(timings)
    metrics = {
        "requests": int(args.requests),
        "p50_ms": float(np.percentile(timings, 50)),
        "p95_ms": float(np.percentile(timings, 95)),
        "p99_ms": float(np.percentile(timings, 99)),
        "mean_ms": float(np.mean(timings)),
    }

    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
