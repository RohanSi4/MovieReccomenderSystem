# 🎬 Personalized Movie Ranking Service

A production-style movie recommendation and ranking system that combines offline
ML training with a low-latency Go service and a lightweight Next.js demo UI.

This is a personal portfolio project designed to mirror real-world MLE systems:
data pipelines, model training, and online ranking at inference time.

## What It Does
- **User mode:** enter a MovieLens `user_id` and get ranked recommendations based
  on that user’s historical ratings.
- **Movie mode:** search by title, pick a movie, and get similar recommendations.
- Uses MovieLens for ratings data and TMDB for metadata/posters.

## Demo Screenshots
![UI overview](docs/ui.png)
![Ranked results](docs/recs.png)

## How It Works
1) **Ingestion + validation** of MovieLens CSVs  
2) **TMDB enrichment** for metadata (genres, popularity, posters, etc.)  
3) **Feature tables** for users and movies  
4) **Model training** with LightGBM (offline)  
5) **Online service** returns ranked results + lightweight explanations  
6) **Frontend UI** calls `/search` and `/rank` and renders cards  

Note: the Go service currently uses a lightweight heuristic score from the
feature tables. The LightGBM model is trained offline and saved to disk; wiring
model inference into Go is a future step.

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
- Ranking + response
              |
              v
Frontend Demo (Next.js)
- Search title or enter user_id
- Call /search and /rank
- Render movie cards
```

## Tech Stack
- **ML pipeline:** Python, LightGBM
- **Online service:** Go
- **Frontend:** Next.js + Tailwind
- **Data:** MovieLens + TMDB API

## Local Run (Dev)
Prereqs: Python 3, Go 1.21+, Node 18+.

Create + activate virtual env (macOS/zsh):
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Makefile shortcuts:
```bash
make help
```

Set your TMDB key (optional but recommended):
```bash
export TMDB_API_KEY=YOUR_KEY_HERE
```

### 1) Build pipeline outputs
```bash
python ml/scripts/ingest_movielens.py --raw-dir ml/data/raw --out-dir ml/data/processed
python ml/scripts/enrich_tmdb.py --processed-dir ml/data/processed --out ml/data/processed/tmdb_enriched.csv
python ml/scripts/build_features.py --processed-dir ml/data/processed --tmdb-csv ml/data/processed/tmdb_enriched.csv --out-dir ml/data/processed/features
python ml/scripts/build_training_dataset.py --processed-dir ml/data/processed --features-dir ml/data/processed/features --out-dir ml/data/processed/training
python ml/scripts/train_lightgbm.py --training-dir ml/data/processed/training --out-dir ml/models
python ml/scripts/export_service_data.py --features-dir ml/data/processed/features --out-dir service/data
```

### 2) (Optional) Run model inference service
```bash
uvicorn model_service.app:app --host 0.0.0.0 --port 8090
```

### 3) Run the Go service
```bash
cd service
MODEL_API_BASE=http://localhost:8090 go run ./cmd/server
```

If you skip the model service, run:
```bash
cd service
go run ./cmd/server
```

### 4) Run the frontend
```bash
cd frontend
npm run dev
```

## API

### Rank Movies
`POST /rank`

User-based request:
```json
{
  "user_id": 123,
  "k": 25
}
```

Movie-based request:
```json
{
  "movie_id": 550,
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

### Search Movies
`GET /search?q=matrix&limit=10`

Response:
```json
[
  { "movie_id": 2571, "title": "Matrix, The (1999)" },
  { "movie_id": 2572, "title": "Matrix Reloaded, The (2003)" }
]
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

## Data Sources
- **MovieLens (25M or 32M):** ratings, tags, timestamps
- **TMDB API:** genres, popularity, vote averages, release year, runtime, posters

## Status
Demo complete and working locally. Model inference integration in Go is optional
future work; the current service ranks using a heuristic over feature tables.

## Metrics (Run to Populate)
Offline quality (NDCG@10, model vs baseline):
```bash
python ml/scripts/evaluate_model.py \
  --training-dir ml/data/processed/training \
  --model-dir ml/models \
  --ndcg-k 10
```

Online-style quality (model vs heuristic):
```bash
python ml/scripts/compare_heuristic_vs_model.py \
  --training-dir ml/data/processed/training \
  --model-dir ml/models \
  --ndcg-k 10
```

Scale (dataset and feature table sizes):
```bash
python ml/scripts/report_dataset_stats.py \
  --processed-dir ml/data/processed \
  --features-dir ml/data/processed/features
```

Latency (p50/p95/p99):
```bash
python service/scripts/benchmark_latency.py --base-url http://localhost:8080 --requests 200 --k 25
```
