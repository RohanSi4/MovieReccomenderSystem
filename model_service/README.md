# Model Inference Service

FastAPI service that loads the LightGBM model and scores candidate movies.

## Run
From repo root:
```bash
source .venv/bin/activate
pip install -r requirements.txt
uvicorn model_service.app:app --host 0.0.0.0 --port 8090
```

Env vars (optional):
- `MODEL_DIR` (default `ml/models`)
- `FEATURES_DIR` (default `ml/data/processed/features`)

## Endpoint
`POST /score`

Body:
```json
{
  "user_id": 123,
  "movie_ids": [1, 2, 3]
}
```
