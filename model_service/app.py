from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List

import lightgbm as lgb
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


class ScoreRequest(BaseModel):
    user_id: int
    movie_ids: List[int]


class ScoreItem(BaseModel):
    movie_id: int
    score: float


class ScoreResponse(BaseModel):
    scores: List[ScoreItem]


def load_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing expected file: {path}")
    return pd.read_parquet(path)


def load_feature_columns(path: Path) -> List[str]:
    if not path.exists():
        raise FileNotFoundError(f"Missing feature list: {path}")
    return json.loads(path.read_text())


def build_feature_frame(
    user_id: int, movie_ids: List[int], users: pd.DataFrame, movies: pd.DataFrame
) -> pd.DataFrame:
    base = pd.DataFrame({"userId": [user_id] * len(movie_ids), "movieId": movie_ids})
    base = base.merge(users, on="userId", how="left")
    base = base.merge(movies, on="movieId", how="left", suffixes=("_user", "_movie"))
    return base


def init_state() -> dict:
    model_dir = Path(os.getenv("MODEL_DIR", "ml/models"))
    features_dir = Path(os.getenv("FEATURES_DIR", "ml/data/processed/features"))

    model_path = model_dir / "lightgbm_model.txt"
    feature_path = model_dir / "feature_columns.json"
    users_path = features_dir / "user_features.parquet"
    movies_path = features_dir / "movie_features.parquet"

    model = lgb.Booster(model_file=str(model_path))
    feature_cols = load_feature_columns(feature_path)
    users = load_parquet(users_path)
    movies = load_parquet(movies_path)

    return {
        "model": model,
        "feature_cols": feature_cols,
        "users": users,
        "movies": movies,
        "user_ids": set(users["userId"].unique()),
    }


app = FastAPI(title="Movie Ranker Model Service")
state = init_state()


@app.post("/score", response_model=ScoreResponse)
def score(req: ScoreRequest) -> ScoreResponse:
    if not req.movie_ids:
        return ScoreResponse(scores=[])

    users = state["users"]
    movies = state["movies"]

    if req.user_id not in state["user_ids"]:
        raise HTTPException(status_code=404, detail="user_id not found")

    features = build_feature_frame(req.user_id, req.movie_ids, users, movies)
    X = features.reindex(columns=state["feature_cols"], fill_value=0).fillna(0)
    scores = state["model"].predict(X)

    results = [
        ScoreItem(movie_id=movie_id, score=float(score))
        for movie_id, score in zip(req.movie_ids, scores)
    ]
    return ScoreResponse(scores=results)
