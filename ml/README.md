# ML Pipeline

This folder contains the offline ML pipeline. Start with data ingestion to validate MovieLens data.

## Quick Start
Create + activate virtual env (macOS/zsh):
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Data Layout
- `ml/data/raw/` should contain the MovieLens CSV files (unzipped).
- `ml/data/processed/` will contain normalized Parquet outputs.

Expected raw files:
- `ratings.csv`
- `movies.csv`
- `tags.csv`
- `links.csv`

## Ingestion
Run:
```bash
python ml/scripts/ingest_movielens.py --raw-dir ml/data/raw --out-dir ml/data/processed
```

This will:
- load CSVs
- validate required columns
- write Parquet outputs
- print basic row counts and ranges

If you want to store the raw dataset elsewhere, pass an absolute path to `--raw-dir`.

## Validation
Run:
```bash
python ml/scripts/validate_movielens.py --processed-dir ml/data/processed
```

This prints sanity checks (row counts, ranges, nulls, and join coverage).

## TMDB Enrichment
Set the API key (do not commit it):
```bash
export TMDB_API_KEY=YOUR_KEY_HERE
```

Run:
```bash
python ml/scripts/enrich_tmdb.py --processed-dir ml/data/processed --out ml/data/processed/tmdb_enriched.csv
```

This fetches a tight set of fields (genres, popularity, vote averages, runtime, poster path, overview).

## Feature Tables
Run:
```bash
python ml/scripts/build_features.py --processed-dir ml/data/processed --out-dir ml/data/processed/features
```

If TMDB enrichment is complete, join it in:
```bash
python ml/scripts/build_features.py \
  --processed-dir ml/data/processed \
  --tmdb-csv ml/data/processed/tmdb_enriched.csv \
  --out-dir ml/data/processed/features
```

If you run TMDB enrichment later, rerun `build_features.py` to include the new columns.

## Training Dataset
Run:
```bash
python ml/scripts/build_training_dataset.py \
  --processed-dir ml/data/processed \
  --features-dir ml/data/processed/features \
  --out-dir ml/data/processed/training
```

This creates `train.parquet` and `val.parquet` using a time-based split.

## Train Ranker
Install deps if needed:
```bash
pip install -r requirements.txt
```

Run:
```bash
python ml/scripts/train_lightgbm.py \
  --training-dir ml/data/processed/training \
  --out-dir ml/models
```

This writes:
- `ml/models/lightgbm_model.txt`
- `ml/models/feature_columns.json`
- `ml/models/metrics.json`

## Export for Go Service
Run:
```bash
python ml/scripts/export_service_data.py \
  --features-dir ml/data/processed/features \
  --out-dir service/data
```

This creates compact CSVs consumed by the Go API.

## Notes
- `user_id` values in the UI come from MovieLens (not a TMDB account).
- The Go service currently uses heuristic scoring over exported features; the
  LightGBM model is trained offline and saved in `ml/models/`.
