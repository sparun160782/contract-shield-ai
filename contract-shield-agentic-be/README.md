# Contract Shield Agent Backend

This module evaluates extracted contract clauses against business rules and writes risk findings to BigQuery.

## What It Reads

- `contract_clauses`
- `contracts`
- `risk_rules`

## What It Writes

- `risk_assessments`

## Assessment Flow

1. Load enabled rules from `risk_rules`.
2. Pull unassessed clauses from BigQuery.
3. Apply deterministic rule-pattern pre-filter.
4. Send clause plus narrowed rules to Gemini.
5. Parse JSON response and store one or more `risk_assessments` rows.

If no rule pattern matches a clause, the agent stores a `risk_flag=false` result so the clause is not retried forever.

## Environment

Copy and edit env file:

```powershell
Copy-Item .env.example .env.local
```

Required variables:

- `GCP_PROJECT_ID`
- `BQ_DATASET`
- `GOOGLE_API_KEY`

Optional variables:

- `MODEL_NAME` (default `gemini-2.5-flash`)
- `MODEL_TEMPERATURE` (default `0.3`)
- `MODEL_MAX_TOKENS` (default `1000`)
- `BATCH_SIZE` (default `10`)
- `QUERY_LIMIT` (default `100`)

## Run

From repository root:

```powershell
make run-agent
```

Or directly:

```powershell
cd contract-shield-agentic-be
python main.py
```
