# Go Ranking Service

Minimal HTTP service that returns ranked movies.

Note: this version uses a lightweight heuristic score from the feature tables.
The LightGBM model is trained offline; wiring model inference into Go is a
separate step.

## Data
The service reads CSVs from `service/data/`:
- `movie_features.csv`
- `user_features.csv`

Generate these from the ML pipeline:
```bash
python ml/scripts/export_service_data.py \
  --features-dir ml/data/processed/features \
  --out-dir service/data
```

## Run
```bash
go run ./cmd/server
```

Env vars:
- `PORT` (default 8080)
- `MOVIE_DATA_DIR` (default auto-detected: `service/data` or `data`)

## Endpoints
- `POST /rank` -> body `{ "user_id": 123, "k": 25 }` (MovieLens user id)  
  or `{ "movie_id": 550, "k": 25 }` (movie-based similar titles)
- `GET /search?q=matrix&limit=10`
- `GET /movie/{movie_id}`
- `GET /health`

## Latency Bench
Run (with server running):
```bash
python service/scripts/benchmark_latency.py --base-url http://localhost:8080 --requests 200 --k 25
```
