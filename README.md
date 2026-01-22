# 🎬 Personalized Movie Ranking Service

A production-style movie recommendation and ranking system that combines offline
ML training with a low-latency Go inference service and a lightweight demo UI.

This is a personal portfolio project designed to mirror real-world MLE systems:
data pipelines, model training, and online ranking at inference time.

## What It Does
- Given a `user_id`, returns a ranked list of movies with scores and brief
  explanation signals.
- Uses MovieLens for ratings data and TMDB for movie metadata/posters.
- Exposes a small HTTP API and a minimal frontend for demoing results.

## Architecture
```
MovieLens Ratings + TMDB Metadata
              |
              v
Offline ML Pipeline (Python)
- Feature engineering
- Model training (LightGBM)
- Offline evaluation
- Model export
              |
              v
Online Ranking Service (Go)
- Candidate generation
- Feature fetching
- Model inference
- Ranking + response
              |
              v
Frontend Demo (Web)
- Select user_id
- Call /rank
- Render movie cards
```

## Tech Stack
- **ML pipeline:** Python, LightGBM
- **Online service:** Go
- **Frontend:** lightweight web UI (framework TBD)
- **Data:** MovieLens + TMDB API

## Local Run (Dev)
1) Build pipeline outputs:
```bash
python ml/scripts/ingest_movielens.py --raw-dir ml/data/raw --out-dir ml/data/processed
python ml/scripts/build_features.py --processed-dir ml/data/processed --out-dir ml/data/processed/features
python ml/scripts/build_training_dataset.py --processed-dir ml/data/processed --features-dir ml/data/processed/features --out-dir ml/data/processed/training
python ml/scripts/train_lightgbm.py --training-dir ml/data/processed/training --out-dir ml/models
python ml/scripts/export_service_data.py --features-dir ml/data/processed/features --out-dir service/data
```

2) Run the Go service:
```bash
go run ./service/cmd/server
```

## API (Draft)

### Rank Movies
`POST /rank`

Request:
```json
{
  "user_id": 123,
  "k": 25
}
```

Response:
```json
{
  "user_id": 123,
  "results": [
    {
      "movie_id": 550,
      "score": 0.91,
      "title": "Fight Club",
      "poster_url": "https://image.tmdb.org/t/p/w342/....jpg",
      "reasons": ["genre_match:thriller", "high_popularity"]
    }
  ],
  "latency_ms": 47
}
```

### Movie Details (Optional)
`GET /movie/{movie_id}`

Response:
```json
{
  "movie_id": 550,
  "title": "Fight Club",
  "release_year": 1999,
  "genres": ["Drama", "Thriller"],
  "tmdb_vote_avg": 8.4,
  "tmdb_popularity": 62.1,
  "poster_url": "https://image.tmdb.org/t/p/w342/....jpg",
  "overview": "..."
}
```

### Feedback (Optional)
`POST /feedback`

Request:
```json
{
  "user_id": 123,
  "movie_id": 550,
  "event_type": "click"
}
```

## Data Sources
- **MovieLens (25M or 32M):** ratings, tags, timestamps
- **TMDB API:** genres, popularity, vote averages, release year, runtime, posters

## Roadmap
- Build the offline training pipeline end-to-end
- Define the feature store and candidate generation path
- Implement the Go inference service with `/rank`
- Add a minimal demo UI for user selection and result display
- Add feedback logging and evaluation metrics

## Status
Work in progress. This README will expand as components land.
