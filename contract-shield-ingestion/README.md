# Contract Shield Ingestion

This module ingests local contract files, extracts text with Document AI, segments clauses, and stores records in BigQuery.

## What It Writes

- `contracts`
- `contract_clauses`
- `processing_audit`

## Prerequisites

- Python 3.10+
- `gcloud` and `bq` CLI authenticated
- Document AI processor configured
- Cloud Storage bucket available
- BigQuery dataset/tables created (use root `make schema-setup`)

## Environment

Copy and edit env file:

```powershell
Copy-Item .env.example .env.local
```

Required variables:

- `GCP_PROJECT_ID`
- `DOCAI_LOCATION`
- `DOCAI_PROCESSOR_ID`
- `GCS_BUCKET`
- `BQ_DATASET`
- `INPUT_FOLDER`

Optional variables:

- `GCS_RAW_PREFIX` (default `raw-contracts`)
- `GCS_EXTRACT_PREFIX` (default `docai-output`)
- `ALLOWED_EXTENSIONS` (default `.pdf`)

## Run

From repository root:

```powershell
make run-ingestion
```

Or directly:

```powershell
cd contract-shield-ingestion
python -m src.main
```

## Rule Seeding

Load risk rules YAML into BigQuery:

```powershell
python -m src.seed_rules
```

Custom file path:

```powershell
python -m src.seed_rules --rules-file C:/path/to/risk_rules.yaml
```

## Notes

- Duplicate prevention is done with SHA-256 hash checks against BigQuery.
- Extraction JSON is saved to GCS and referenced by `contracts.extracted_text_uri`.
- Clause segmentation is heuristic and intended for the assignment mock contracts.
