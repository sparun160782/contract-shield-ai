# Contract Shield AI - Enterprise Contract Risk Assessment

A comprehensive platform for automated contract risk assessment that combines Google Document AI for text extraction, BigQuery for data management, and an ADK agent powered by Gemini for intelligent risk evaluation.

## Demo:

Click on the above video to have A short walkthrough of the Contract Shield Risk Assessment. 

[![YouTube](https://img.shields.io/badge/YouTube-Watch%20Demo-red?logo=youtube)](https://youtu.be/nfBUR-wUU8c?si=XEwHuKb2nwShobsj)

[![Contract Shield AI - Watch the demo](https://img.youtube.com/vi/nfBUR-wUU8c/maxresdefault.jpg)](https://youtu.be/nfBUR-wUU8c?si=XEwHuKb2nwShobsj)


## System Overview

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ Contract Shield AI - Complete Pipeline                          │
└─────────────────────────────────────────────────────────────────┘

Stage 1: INGESTION & EXTRACTION
├─ Local folder scanner (duplicate detection via SHA-256)
├─ Cloud Storage upload  
├─ Google Document AI (OCR + text extraction)
└─ BigQuery storage (contracts, clauses metadata)

Stage 2: RISK ASSESSMENT
├─ ADK Agent retrieval of clauses
├─ Business rule loading & pattern matching
├─ Gemini LLM evaluation
└─ Risk classification (severity, category, confidence)

Stage 3: REVIEW & ACTION
├─ Dashboard for legal teams
├─ Flagged clauses with evidence & recommendations
└─ Audit trail and compliance records
```

## Quick Start

### Prerequisites

- Python 3.10+
- GCP project with Document AI, BigQuery, Cloud Storage enabled
- `gcloud` CLI configured
- Google API key for Gemini (or Application Default Credentials)

### Setup (One-Time)

```bash
# Navigate to project root
cd contract-shield-ai

# Check environment
make env-check

# Complete setup (installs deps, creates BQ schema, seeds rules)
make setup

# Create input directory and add PDF contracts
mkdir contract_input_pack
cp your-contracts/*.pdf contract_input_pack/
```

### Run the Pipeline

```bash
# Full pipeline: ingestion → assessment
make run-all

# Or run individually:
make run-ingestion   # Extract and store contracts
make run-agent       # Assess risks
```

## Project Structure

```
contract-shield-ai/
├── Makefile                           # Development tasks
├── contract-shield-ingestion/         # Extraction pipeline
│   ├── src/
│   │   ├── main.py                   # Pipeline orchestrator
│   │   ├── config.py                 # Configuration management
│   │   ├── file_scanner.py           # Local file scanning & dedup
│   │   ├── document_processor.py      # Document AI integration
│   │   ├── clause_normalizer.py      # Text segmentation
│   │   ├── bigquery_loader.py        # BQ data loading
│   │   └── audit_logger.py           # Audit trail logging
│   ├── pyproject.toml
│   ├── .env.example
│   └── README.md
│
├── contract-shield-agentic-be/       # Risk assessment agent
│   ├── src/
│   │   ├── risk_assessment_agent.py   # Main agent orchestrator
│   │   ├── agent_config.py           # Agent configuration
│   │   ├── rule_engine.py            # Business rule management
│   │   ├── prompt_builder.py         # LLM prompt engineering
│   │   └── __init__.py
│   ├── main.py                       # Entry point
│   ├── pyproject.toml
│   ├── .env.example
└── └── README.md
```

## Configuration

### Ingestion Pipeline (.env.local)

```bash
cp contract-shield-ingestion/.env.example contract-shield-ingestion/.env.local
```

Edit `.env.local`:

```env
GCP_PROJECT_ID=your-project-id
DOCAI_LOCATION=us
DOCAI_PROCESSOR_ID=your-processor-id  # Create in Document AI console
GCS_BUCKET=your-bucket-name
BQ_DATASET=contract_risk
INPUT_FOLDER=./contract_input_pack
```

### Agent Backend (.env.local)

```bash
cp contract-shield-agentic-be/.env.example contract-shield-agentic-be/.env.local
```

Edit `.env.local`:

```env
GCP_PROJECT_ID=your-project-id
BQ_DATASET=contract_risk
MODEL_NAME=gemini-2.5-flash
GOOGLE_API_KEY=your-gemini-api-key  # Or use Application Default Credentials
```

## Data Model

### Key Tables

**contracts**
- `contract_id` (PK): Unique contract identifier
- `file_name`, `file_hash`: Source tracking
- `upload_time`, `extraction_status`: Pipeline tracking
- `total_pages`, `extracted_text_uri`: Content reference

**contract_clauses**
- `clause_id` (PK): Unique clause identifier  
- `contract_id` (FK): Parent contract
- `clause_text`: Full clause content
- `clause_title`, `section_name`: Organization

**risk_rules**
- `rule_id` (PK): Rule identifier
- `rule_name`, `rule_category`: Description
- `risky_patterns[]`: Deterministic pattern matches
- `severity_default`: Risk level (Critical/High/Medium/Low)

**risk_assessments**
- `assessment_id` (PK): Assessment record identifier
- `clause_id`, `rule_id` (FKs): Assessed clause and rule
- `risk_flag`: Boolean risk determination
- `severity`, `confidence_score`: Risk classification
- `rationale`, `evidence_text`: Explanation
- `recommended_action`: Remediation guidance

**processing_audit**
- `event_id` (PK): Event identifier
- `contract_id` (FK): Associated contract
- `step_name`, `status`: Pipeline tracking
- `timestamp`, `message`: Event details

## Usage

### 1. Ingestion Pipeline

Automatically extracts and stores contracts:

```bash
# Scans contract_input_pack/
# Deduplicates by SHA-256 hash
# Uploads to GCS
# Processes with Document AI
# Stores in BigQuery
make run-ingestion
```

**Output:**
- BigQuery `contracts` table: 1 row per file
- BigQuery `contract_clauses` table: ~5-100 rows per contract
- GCS raw and extraction artifacts: Audit trail

### 2. Risk Assessment Agent

Evaluates clauses against business rules:

```bash
# Retrieves unassessed clauses from BigQuery
# Applies pattern matching to narrow rules
# Sends to Gemini for LLM reasoning
# Stores risk classifications
make run-agent
```

**Output:**
- BigQuery `risk_assessments` table: 1+ rows per clause
- Classification: risk_flag, severity (Critical/High/Medium/Low)
- Evidence & recommendations

### 3. Dashboard / Review

Query results:

```sql
SELECT
  c.contract_id,
  c.file_name,
  COUNT(a.risk_flag) as risk_count,
  ARRAY_AGG(DISTINCT a.severity) as severities
FROM contract_risk.contracts c
LEFT JOIN contract_risk.risk_assessments a 
  ON c.contract_id = a.contract_id
WHERE a.risk_flag = true
GROUP BY 1, 2
ORDER BY risk_count DESC;
```

## Makefile Commands

```bash
make help                # Show all commands
make env-check          # Verify prerequisites
make setup              # One-time setup (deps + BQ + rules)
make install            # Install Python dependencies
make cloud-auth         # Authenticate with GCP

make schema-setup       # Create BigQuery schema
make seed-rules         # Load risk rules
make run-ingestion      # Run extraction pipeline
make run-agent          # Run assessment agent
make run-all            # Full pipeline

make lint              # Linting checks
make format            # Code formatting
make test              # Run tests
make docs              # Generate documentation

make clean             # Clean build artifacts
make clean-all         # Full cleanup
```

## Risk Categories

The system evaluates against these risk categories:

- **Renewal Risk**: Auto-renewal with onerous notice periods
- **Liability Risk**: Unlimited or uncapped liability exposure
- **Termination Risk**: One-sided or restrictive termination terms
- **Confidentiality Risk**: Weak or missing confidentiality protections
- **Privacy Risk**: Insufficient data protection controls
- **Security Risk**: Weak security commitments
- **Compliance Risk**: Restricted audit or assurance rights
- **Jurisdiction Risk**: Unfavorable governing law/jurisdiction

## Workflow Example

```
1. Place contracts in contract_input_pack/
   ├─ contract_1.pdf
   ├─ contract_2.pdf
   └─ contract_3.pdf

2. Run: make run-ingestion
   ├─ Scans & deduplicates files
   ├─ Uploads to GCS
   ├─ Processes with Document AI
   └─ Stores in BigQuery

3. Review extraction:
   SELECT contract_id, file_name, total_pages 
   FROM contract_risk.contracts;

4. Run: make run-agent
   ├─ Loads clauses from BigQuery
   ├─ Applies business rules
   ├─ Evaluates with Gemini
   └─ Stores risk assessments

5. Query results:
   SELECT * FROM contract_risk.risk_assessments
   WHERE risk_flag = true
   ORDER BY severity DESC;

6. Review in your dashboard/tool of choice
```

## Performance & Scaling

- **Ingestion**: ~1-3 minutes per document (Document AI processing)
- **Assessment**: ~5-10 seconds per clause (Gemini API)
- **BigQuery**: Handles 100K+ contracts efficiently

For production:
- Batch processing in Dataflow for >1000 contracts
- Implement queue-based processing (Cloud Tasks)
- Monitor Document AI quotas
- Cache rule evaluations

## Troubleshooting

### "GCP_PROJECT_ID not set"
```bash
export GCP_PROJECT_ID=your-project-id
# or add to .env.local
```

### "DOCAI_PROCESSOR_ID not set"
1. Go to GCP Console → Document AI
2. Create processor (type: "Generalist Document Parser")
3. Copy Processor ID
4. Set: `export DOCAI_PROCESSOR_ID=projects/PROJECT/locations/LOCATION/processors/ID`

### "No credentials found"
```bash
gcloud auth application-default login
```

### "BigQuery permission denied"
Ensure service account has:
- `bigquery.dataEditor`
- `bigquery.jobUser`
- `storage.objectViewer`

## Next Steps

- [ ] Set up Cloud Scheduler for recurring ingestion
- [ ] Build review dashboard with Looker/Data Studio
- [ ] Add more sophisticated rule matching (regex, semantic)
- [ ] Implement feedback loop (user corrections → model improvement)
- [ ] Add SLA tracking and compliance reporting
- [ ] Integrate with contract management system
- [ ] Add support for structured data extraction (parties, dates, amounts)

## Support

For issues, enhancements, or questions:
1. Check Makefile commands: `make help`
2. Review logs: Check console output during pipeline runs
3. Query BigQuery for audit trail: `SELECT * FROM processing_audit`

## License

[Add your license here]

---

**Last Updated:** June 21, 2026
**Version:** 0.1.0
