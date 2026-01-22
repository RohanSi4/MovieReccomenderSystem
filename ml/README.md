# ML Pipeline

This folder contains the offline ML pipeline. Start with data ingestion to validate MovieLens data.

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
