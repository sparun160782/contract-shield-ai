-- BigQuery schema for Enterprise Contract Risk Assessor
-- Update project and dataset names before execution if required.

CREATE SCHEMA IF NOT EXISTS `your-project-id.contract_risk` OPTIONS(location="US");

CREATE TABLE IF NOT EXISTS `your-project-id.contract_risk.contracts` (
  contract_id STRING NOT NULL,
  file_name STRING NOT NULL,
  file_path STRING,
  file_hash STRING NOT NULL,
  file_size_bytes INT64,
  upload_time TIMESTAMP,
  document_type STRING,
  extraction_status STRING,
  total_pages INT64,
  extracted_text_uri STRING,
  raw_gcs_uri STRING,
  processing_batch_id STRING,
  source_system STRING,
  created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS `your-project-id.contract_risk.contract_clauses` (
  clause_id STRING NOT NULL,
  contract_id STRING NOT NULL,
  clause_number STRING,
  clause_title STRING,
  clause_text STRING,
  page_number INT64,
  section_name STRING,
  created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS `your-project-id.contract_risk.risk_rules` (
  rule_id STRING NOT NULL,
  rule_name STRING NOT NULL,
  rule_category STRING NOT NULL,
  rule_description STRING,
  risky_patterns ARRAY<STRING>,
  expected_condition STRING,
  severity_default STRING,
  enabled_flag BOOL,
  rule_version STRING,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS `your-project-id.contract_risk.risk_assessments` (
  assessment_id STRING NOT NULL,
  contract_id STRING NOT NULL,
  clause_id STRING,
  rule_id STRING,
  risk_flag BOOL,
  severity STRING,
  confidence_score FLOAT64,
  rationale STRING,
  evidence_text STRING,
  recommended_action STRING,
  assessor_type STRING,
  assessment_status STRING,
  assessed_at TIMESTAMP,
  model_name STRING,
  batch_id STRING
);

CREATE TABLE IF NOT EXISTS `your-project-id.contract_risk.processing_audit` (
  event_id STRING NOT NULL,
  contract_id STRING NOT NULL,
  step_name STRING NOT NULL,
  status STRING NOT NULL,
  timestamp TIMESTAMP NOT NULL,
  message STRING,
  batch_id STRING
);

-- Useful views
CREATE OR REPLACE VIEW `your-project-id.contract_risk.v_contract_risk_summary` AS
SELECT
  c.contract_id,
  c.file_name,
  c.document_type,
  c.extraction_status,
  COUNTIF(a.risk_flag) AS risk_hits,
  ARRAY_AGG(DISTINCT a.severity IGNORE NULLS) AS severities,
  MAX(a.assessed_at) AS last_assessed_at
FROM `your-project-id.contract_risk.contracts` c
LEFT JOIN `your-project-id.contract_risk.risk_assessments` a
  ON c.contract_id = a.contract_id
GROUP BY 1,2,3,4;
