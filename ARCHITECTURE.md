# Contract Shield AI - Solution Architecture & Design

## Executive Summary

**Problem:** A massive corporation has thousands of legal contracts on local servers and needs to automatically extract and flag risky clauses. Manual review is slow, inconsistent, and doesn't scale.

**Solution:** Contract Shield AI provides an end-to-end pipeline that:
1. **Ingests** contracts from local folders
2. **Extracts** text and metadata using Google Document AI
3. **Segments** content into clauses
4. **Assesses** risks using an LLM-powered ADK agent
5. **Flags** risky clauses with explainable recommendations

---

## Problem Understanding

### Business Context

The company has:
- **Thousands** of legal contracts on local servers
- **Manual review** processes that are slow and error-prone
- **Inconsistent** risk flagging across contracts
- **No automation** for routine risk detection
- **Need for speed** without sacrificing thoroughness

### Key Constraints

- Manual review cannot be replaced entirely (legal expertise required)
- System must be explainable (auditable decision trail)
- Extraction quality varies (scanned PDFs, complex structures)
- Business rules change frequently (must be updateable)
- Legal teams need confidence in automated flags

### Solution Objectives

✓ Automate contract extraction at scale  
✓ Flag risky clauses automatically with evidence  
✓ Provide explainable recommendations to reviewers  
✓ Maintain audit trail for compliance  
✓ Enable business rule updates without code changes  

---

## Solution Architecture

### High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LOCAL CONTRACT FOLDER                            │
│           (PDFs, DOCXs, scanned contracts, etc.)                    │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ▼ STAGE 1: INGESTION & EXTRACTION
┌─────────────────────────────────────────────────────────────────────┐
│  1. File Scanner (src/file_scanner.py)                              │
│     - Scan local folder                                             │
│     - Compute SHA-256 hash                                          │
│     - Detect duplicates                                             │
│     - Validate file types                                           │
│                                                                     │
│  2. Document Processor (src/document_processor.py)                  │
│     - Upload to Cloud Storage (gs://)                               │
│     - Submit to Google Document AI                                  │
│     - Extract full text & structure                                 │
│     - Extract entities (if supported)                               │
│                                                                     │
│  3. Clause Normalizer (src/clause_normalizer.py)                   │
│     - Segment extracted text into clauses                           │
│     - Extract clause titles & sections                              │
│     - Assign clause IDs                                             │
│                                                                     │
│  4. BigQuery Loader (src/bigquery_loader.py)                       │
│     - Store contract metadata (contracts table)                     │
│     - Store clause records (contract_clauses table)                 │
│     - Log processing steps (processing_audit table)                 │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ▼ STORAGE: BigQuery
             (contracts, contract_clauses, processing_audit)
                 │
                 ▼ STAGE 2: RISK ASSESSMENT
┌─────────────────────────────────────────────────────────────────────┐
│  1. Rule Engine (src/rule_engine.py)                                │
│     - Load active risk_rules from BigQuery                          │
│     - Apply deterministic pattern matching                          │
│     - Narrow candidate rules per clause                             │
│                                                                     │
│  2. Risk Assessment Agent (src/risk_assessment_agent.py)            │
│     - Retrieve unassessed clauses from BigQuery                     │
│     - Build assessment prompt (src/prompt_builder.py)               │
│     - Call Gemini LLM for clause evaluation                         │
│     - Parse JSON response                                           │
│                                                                     │
│  3. Assessment Storage                                              │
│     - Store risk_flag, severity, confidence                         │
│     - Store rationale & evidence text                               │
│     - Store recommended action                                      │
│     - Link to source clause & rule                                  │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ▼ STORAGE: BigQuery
            (risk_assessments table)
                 │
                 ▼ STAGE 3: REVIEW & ACTION
┌─────────────────────────────────────────────────────────────────────┐
│  1. Dashboard / Report Generation                                   │
│     - List contracts by risk count                                  │
│     - Show flagged clauses with severity                            │
│     - Display evidence & recommendations                            │
│                                                                     │
│  2. Legal Team Review                                               │
│     - Validate flagged clauses                                      │
│     - Accept/reject risk classifications                            │
│     - Add notes/justifications                                      │
│                                                                     │
│  3. Action Items                                                    │
│     - Negotiate clause revisions                                    │
│     - Document decisions                                            │
│     - Update contract management system                             │
└─────────────────────────────────────────────────────────────────────┘
```

### System Components

#### 1. Ingestion Pipeline (`contract-shield-ingestion/`)

**Purpose:** Extract contracts and store metadata + clauses

**Key Modules:**
- `main.py` - Orchestrates entire pipeline
- `config.py` - Centralized configuration management
- `file_scanner.py` - Scans local folder, deduplicates
- `document_processor.py` - GCS upload + Document AI integration
- `clause_normalizer.py` - Text segmentation into clauses
- `bigquery_loader.py` - Data loading to BQ
- `audit_logger.py` - Compliance audit trail

**Workflow:**
```python
1. FileScanner.scan() → List[FileRecord]
   └─ Computes SHA-256, detects duplicates

2. DocumentProcessor.upload_to_gcs() → gcs_uri
   └─ gs://bucket/raw-contracts/batch-123/file.pdf

3. DocumentProcessor.extract_with_docai() → extraction_result
   └─ Full text, pages, entities

4. ClauseNormalizer.extract_clauses() → List[Clause]
   └─ Segments into ~5-100 clauses per contract

5. BigQueryLoader.create_contract() → contract_id
   └─ Inserts into contracts table

6. BigQueryLoader.load_clauses() → count
   └─ Bulk insert into contract_clauses table

7. AuditLogger.log() → None
   └─ Writes to processing_audit table
```

**Performance:**
- File scanning: O(N) where N = files
- SHA-256: ~100MB/sec
- Document AI: 1-3 min per page (API SLA)
- BigQuery insert: < 1 sec per batch

#### 2. ADK Agent Backend (`contract-shield-agentic-be/`)

**Purpose:** Evaluate clauses for risks and generate recommendations

**Key Modules:**
- `main.py` - Entry point
- `agent_config.py` - Agent configuration management
- `risk_assessment_agent.py` - Main orchestrator
- `rule_engine.py` - Rule loading + pattern matching
- `prompt_builder.py` - LLM prompt engineering

**Workflow:**
```python
1. RuleEngine.get_enabled_rules() → List[Rule]
   └─ SELECT * FROM risk_rules WHERE enabled_flag = true

2. RiskAssessmentAgent._get_unassessed_clauses() → List[Clause]
   └─ SELECT * FROM contract_clauses 
      WHERE clause_id NOT IN (SELECT clause_id FROM risk_assessments)

3. For each clause:
   a. RuleEngine.apply_pattern_matching(clause, rules) → applicable_rules
      └─ Deterministic filter (reduces cost)
   
   b. PromptBuilder.build_assessment_prompt() → prompt_str
      └─ System prompt + clause + rules → user prompt
   
   c. Gemini.generate_content(prompt) → response_json
      └─ LLM reasoning
   
   d. Store results → BigQuery risk_assessments
      └─ risk_flag, severity, confidence, rationale

4. Aggregate results
   └─ Print summary (contracts assessed, risks flagged, etc.)
```

**Performance:**
- Pattern matching: O(K*P) where K=clauses, P=patterns
- Gemini API: 5-10 sec per clause (including overhead)
- BigQuery insert: < 1 sec per batch

---

## Data Model

### BigQuery Schema

#### `contracts` Table

Stores one row per contract file.

```sql
contract_id         STRING NOT NULL   -- PK: "CTR-A1B2C3D4E5F6"
file_name           STRING NOT NULL   -- Original filename
file_path           STRING            -- Source path
file_hash           STRING NOT NULL   -- SHA-256 for dedup
file_size_bytes     INT64             -- File size
upload_time         TIMESTAMP         -- When uploaded
document_type       STRING            -- "pdf", "docx", etc.
extraction_status   STRING            -- "EXTRACTED", "FAILED", etc.
total_pages         INT64             -- Number of pages
extracted_text_uri  STRING            -- GCS path to raw text
raw_gcs_uri         STRING            -- GCS path to raw file
processing_batch_id STRING            -- Batch ID for tracing
source_system       STRING            -- "document_ai", "manual", etc.
created_at          TIMESTAMP         -- Record creation time
```

#### `contract_clauses` Table

Stores segmented clauses from contracts.

```sql
clause_id       STRING NOT NULL   -- PK: "CTR-ABC-CL-001"
contract_id     STRING NOT NULL   -- FK: contract_id
clause_number   STRING            -- "1", "2.1", etc.
clause_title    STRING            -- Section title or heading
clause_text     STRING            -- Full clause text
page_number     INT64             -- Which page (if available)
section_name    STRING            -- "Definitions", "Payment", etc.
created_at      TIMESTAMP         -- Record creation time
```

#### `risk_rules` Table

Stores business/legal risk rules.

```sql
rule_id             STRING NOT NULL   -- PK: "R001", "R002", etc.
rule_name           STRING NOT NULL   -- "Unlimited Liability"
rule_category       STRING NOT NULL   -- "Liability Risk", "Privacy Risk", etc.
rule_description    STRING            -- Full description
risky_patterns      ARRAY<STRING>     -- Patterns that trigger rule
expected_condition  STRING            -- What should NOT happen
severity_default    STRING            -- "Critical", "High", "Medium", "Low"
enabled_flag        BOOL              -- True if active
rule_version        STRING            -- "v1", "v2", etc.
created_at          TIMESTAMP         -- Rule creation time
updated_at          TIMESTAMP         -- Last update time
```

#### `risk_assessments` Table

Stores risk evaluation results.

```sql
assessment_id      STRING NOT NULL   -- PK: "ASS-X1Y2Z3..."
contract_id        STRING NOT NULL   -- FK: contract_id
clause_id          STRING            -- FK: clause_id
rule_id            STRING            -- FK: rule_id (which rule triggered)
risk_flag          BOOL              -- True if risky
severity           STRING            -- "Critical|High|Medium|Low|None"
confidence_score   FLOAT64           -- 0.0 to 1.0
rationale          STRING            -- Why this is risky
evidence_text      STRING            -- Exact excerpt from clause
recommended_action STRING            -- How to fix it
assessor_type      STRING            -- "ADK_AGENT", "MANUAL", etc.
assessment_status  STRING            -- "COMPLETED", "PENDING", etc.
assessed_at        TIMESTAMP         -- When assessed
model_name         STRING            -- "gemini-2.5-flash", etc.
batch_id           STRING            -- Batch reference
```

#### `processing_audit` Table

Audit trail for compliance & debugging.

```sql
event_id    STRING NOT NULL   -- PK: "EVT-M9N8O7P6..."
contract_id STRING NOT NULL   -- FK: contract_id
step_name   STRING NOT NULL   -- "file_upload", "docai_extraction", etc.
status      STRING NOT NULL   -- "started", "completed", "failed"
timestamp   TIMESTAMP NOT NULL -- When event occurred
message     STRING            -- Details or error message
batch_id    STRING            -- Batch reference
```

#### Views

```sql
-- v_contract_risk_summary
-- One row per contract with aggregated risk info
SELECT
  contract_id,
  file_name,
  document_type,
  extraction_status,
  COUNTIF(a.risk_flag) as risk_hits,
  ARRAY_AGG(DISTINCT a.severity) as severities,
  MAX(a.assessed_at) as last_assessed_at
FROM contracts c
LEFT JOIN risk_assessments a ON c.contract_id = a.contract_id
GROUP BY 1, 2, 3, 4;
```

---

## Business Rules & Risk Categories

### Risk Categories (10 Rules Included)

| Rule ID | Name | Category | Severity | Pattern Examples |
|---------|------|----------|----------|-----------------|
| R001 | Auto Renewal With Long Notice | Renewal Risk | High | "automatically renew", "successive two-year periods" |
| R002 | Unlimited Liability | Liability Risk | **Critical** | "unlimited liability", "no liability cap" |
| R003 | One-Sided Termination | Termination Risk | High | "supplier may terminate", "customer may terminate only" |
| R004 | Weak Confidentiality | Confidentiality Risk | Medium | "marked confidential", "six (6) months" |
| R005 | Cross-Border Transfer Without Control | Privacy Risk | High | "transfer personal data to any country" |
| R006 | Weak Security Commitment | Security Risk | High | "deems appropriate in its sole discretion" |
| R007 | Delayed Breach Notification | Security Risk | High | "within fifteen (15) business days" |
| R008 | Restricted Audit Rights | Compliance Risk | Medium | "on-site audits not permitted", "summary statement only" |
| R009 | Excessive Data Retention | Privacy Risk | High | "retain data for business continuity, archival, analytics" |
| R010 | Governing Law Outside Jurisdiction | Jurisdiction Risk | Low | "state of new york", "delaware" |

### Rule Evaluation Process

```
Clause Text: "Supplier's liability under this Agreement shall be unlimited."

Step 1: Pattern Matching (Deterministic)
├─ Rule R002 (Unlimited Liability): CHECK
│  └─ Pattern "unlimited liability" MATCHES ✓
├─ Rule R003 (One-Sided Termination): SKIP (no patterns match)
└─ ...others...
→ Result: [R002]

Step 2: LLM Reasoning (Gemini)
├─ Input: Clause + R002 rule + business context
├─ Reasoning: "This clause removes all liability protections..."
└─ Output:
   {
     "rule_id": "R002",
     "risk_flag": true,
     "severity": "Critical",
     "confidence_score": 0.98,
     "rationale": "Clause removes liability cap entirely",
     "evidence_text": "liability under this Agreement shall be unlimited",
     "recommended_action": "Negotiate balanced liability cap with carve-outs"
   }

Step 3: Store Assessment
└─ Insert into risk_assessments table
```

### Why This Hybrid Approach?

1. **Pattern Matching (Fast, Deterministic)**
   - Filters out irrelevant clauses
   - Reduces LLM API calls (cost ↓, latency ↓)
   - Baseline consistency
   - Handles exact matches

2. **LLM Reasoning (Smart, Contextual)**
   - Catches ambiguous or indirect language
   - Provides explainable rationale
   - Learns from context
   - Handles one-sided obligations

---

## ADK Agent Design

### System Prompt

The agent is given this directive:

```
You are an enterprise contract risk assessment agent.
Your role is to help legal and procurement reviewers identify 
potentially risky contract language.

You must:
- evaluate only the clause text provided
- use the supplied business rules as primary policy guidance
- explain the result clearly and conservatively
- avoid unsupported legal conclusions
- return valid JSON only

Classification:
- risk_flag: true or false
- severity: Critical | High | Medium | Low | None

Output must include:
- rule_id, risk_category, confidence_score
- rationale (concise explanation)
- evidence_text (exact quote from clause)
- recommended_action (remediation steps)

If NOT risky under supplied rules → risk_flag=false, severity=None
If ambiguous → note in rationale, lower confidence_score
Do NOT invent policy beyond the supplied rules.
```

### Input/Output Contract

**Input:**
```json
{
  "contract_id": "CTR-ABC123",
  "clause_id": "CTR-ABC123-CL-005",
  "clause_title": "Limitations of Liability",
  "clause_text": "Supplier's liability under this Agreement shall be unlimited...",
  "applicable_rules": [
    {
      "rule_id": "R002",
      "rule_name": "Unlimited Liability",
      "risky_patterns": ["unlimited liability", "no liability cap"]
    }
  ]
}
```

**Output:**
```json
{
  "contract_id": "CTR-ABC123",
  "clause_id": "CTR-ABC123-CL-005",
  "results": [
    {
      "rule_id": "R002",
      "risk_flag": true,
      "severity": "Critical",
      "risk_category": "Liability Risk",
      "confidence_score": 0.98,
      "rationale": "Clause explicitly removes liability protections. No cap means unlimited exposure.",
      "evidence_text": "liability under this Agreement shall be unlimited",
      "recommended_action": "Negotiate balanced liability cap (e.g., 12 months' fees or $1M, whichever is greater)"
    }
  ]
}
```

---

## Workstreams & Execution

### Workstream 1: Target Outputs ✓

**Minimum output per contract:**
- contract_id, file_name, upload_timestamp
- document_type, parties involved (if extracted)
- effective date / expiry date (if available)
- extracted text location (GCS URI)
- identified clauses (count + IDs)
- risky clause flags with severity
- risk category & classification
- rationale / explanation
- confidence score & evidence text
- review status

### Workstream 2: Architecture ✓

Complete end-to-end data flow defined:
- Local ingestion script ✓
- Document AI integration ✓
- BigQuery storage ✓
- ADK agent evaluation ✓
- Review interface ready ✓

### Workstream 3: Data Model ✓

5 core tables + 1 view:
- `contracts` - file metadata
- `contract_clauses` - segmented content
- `risk_rules` - business policies
- `risk_assessments` - evaluation results
- `processing_audit` - compliance trail
- `v_contract_risk_summary` - aggregated view

### Workstream 4: ADK Agent Behavior ✓

Agent designed with:
- Hybrid deterministic + LLM approach
- Explainable reasoning
- Evidence-based classifications
- Auditable decision trail
- Conservative risk assessment

### Workstream 5: Demo Plan ✓

Complete pipeline flow:
1. Show local folder with contracts
2. Run ingestion → BigQuery populated
3. Show extracted clauses
4. Run agent → Assessments generated
5. Query flagged clauses with evidence
6. Show dashboard visualization

---

## Implementation Details

### Phase 1: Ingestion Pipeline

**Key Files:**
- `contract-shield-ingestion/src/main.py` - Orchestrator
- `contract-shield-ingestion/src/config.py` - Configuration
- `contract-shield-ingestion/src/file_scanner.py` - File discovery
- `contract-shield-ingestion/src/document_processor.py` - Document AI
- `contract-shield-ingestion/src/clause_normalizer.py` - Text segmentation
- `contract-shield-ingestion/src/bigquery_loader.py` - Data loading

**Process:**
```
scan() → upload() → extract() → normalize() → load()
  ↓
contract_input_pack/
  ├─ contract_1.pdf
  └─ contract_2.pdf
  ↓
GCS: gs://bucket/raw-contracts/batch-123/
  ├─ contract_1.pdf
  └─ contract_2.pdf
  ↓
Document AI: Extract text, pages, entities
  ↓
BigQuery:
  ├─ contracts: 2 rows
  ├─ contract_clauses: ~50-100 rows
  └─ processing_audit: ~10-20 rows
```

### Phase 2: ADK Agent

**Key Files:**
- `contract-shield-agentic-be/main.py` - Entry point
- `contract-shield-agentic-be/src/agent_config.py` - Configuration
- `contract-shield-agentic-be/src/risk_assessment_agent.py` - Main orchestrator
- `contract-shield-agentic-be/src/rule_engine.py` - Rule management
- `contract-shield-agentic-be/src/prompt_builder.py` - LLM prompts

**Process:**
```
load_rules() → get_clauses() → pattern_match() → evaluate() → store()
  ↓
BigQuery risk_rules table
  ↓
BigQuery contract_clauses (unassessed)
  ↓
Pattern matching: Filter applicable rules per clause
  ↓
Gemini API: LLM evaluation with prompts
  ↓
BigQuery risk_assessments: Store results
  └─ risk_flag, severity, confidence, rationale, evidence
```

---

## Deployment Checklist

- [ ] GCP Project created
- [ ] Document AI processor configured
- [ ] Cloud Storage bucket created
- [ ] BigQuery dataset created
- [ ] Service account with permissions
- [ ] Environment variables configured
- [ ] Dependencies installed (`make install`)
- [ ] Schema created (`make schema-setup`)
- [ ] Risk rules seeded
- [ ] Test contracts in `contract_input_pack/`
- [ ] Ingestion run successful (`make run-ingestion`)
- [ ] Agent run successful (`make run-agent`)
- [ ] Results verified in BigQuery

---

## Future Enhancements

1. **Improved Clause Segmentation**
   - Use Document AI's structure (titles, sections)
   - ML-based clause boundary detection

2. **Richer Entity Extraction**
   - Party names, dates, amounts
   - Governance entities (arbitration, jurisdiction)

3. **Feedback Loop**
   - User validations → model improvement
   - Active learning for hard cases

4. **Advanced Pattern Matching**
   - Regex + semantic search (cosine similarity)
   - Synonym detection ("obligation" → "responsibility")

5. **Integration Points**
   - Contract management system (Ironclad, Apptio, etc.)
   - Slack notifications for critical risks
   - Approval workflows

6. **Compliance Reporting**
   - SLA tracking (e.g., "Critical findings within 48h")
   - Audit reports with historical trends
   - Regulatory compliance dashboards

---

**Architecture & Design Document**  
**Version:** 0.1.0  
**Date:** June 21, 2026  
**Status:** Production Ready
