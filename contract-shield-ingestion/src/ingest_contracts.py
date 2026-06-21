#!/usr/bin/env python3
"""
Local-folder ingestion script for Enterprise Contract Risk Assessor.

What it does
------------
1. Scans a local folder for contract files (PDF by default)
2. Computes SHA-256 hash for deduplication
3. Uploads new files to Cloud Storage
4. Submits them to Google Document AI for OCR/text extraction
5. Normalises extracted text into clause-level records
6. Loads contract metadata, clauses, and audit records into BigQuery

Notes
-----
- This is a practical starter script aligned to the mock input pack.
- Replace project/location/processor/dataset/bucket settings via env vars.
- The script assumes Google credentials are already configured.
"""

from __future__ import annotations
import os
import re
import json
import time
import uuid
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List, Dict, Any, Optional

from google.cloud import storage
from google.cloud import documentai
from google.cloud import bigquery

# --------------------------
# Configuration via env vars
# --------------------------
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "your-project-id")
LOCATION = os.getenv("DOCAI_LOCATION", "us")
PROCESSOR_ID = os.getenv("DOCAI_PROCESSOR_ID", "your-processor-id")
GCS_BUCKET = os.getenv("GCS_BUCKET", "your-contract-risk-bucket")
BQ_DATASET = os.getenv("BQ_DATASET", "contract_risk")
INPUT_FOLDER = os.getenv("INPUT_FOLDER", "./contract_input_pack")
RAW_PREFIX = os.getenv("GCS_RAW_PREFIX", "raw-contracts")
EXTRACT_PREFIX = os.getenv("GCS_EXTRACT_PREFIX", "docai-output")
ALLOWED_EXTENSIONS = {".pdf"}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("contract_ingestion")

storage_client = storage.Client(project=PROJECT_ID)
docai_client = documentai.DocumentProcessorServiceClient()
bq_client = bigquery.Client(project=PROJECT_ID)


@dataclass
class FileRecord:
    file_path: str
    file_name: str
    extension: str
    file_size_bytes: int
    sha256: str
    modified_at: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def compute_sha256(file_path: str) -> str:
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha.update(chunk)
    return sha.hexdigest()


def scan_folder(input_folder: str) -> List[FileRecord]:
    records: List[FileRecord] = []
    for entry in sorted(os.listdir(input_folder)):
        file_path = os.path.join(input_folder, entry)
        if not os.path.isfile(file_path):
            continue
        _, ext = os.path.splitext(entry)
        ext = ext.lower()
        if ext not in ALLOWED_EXTENSIONS:
            continue
        stat = os.stat(file_path)
        records.append(
            FileRecord(
                file_path=file_path,
                file_name=entry,
                extension=ext,
                file_size_bytes=stat.st_size,
                sha256=compute_sha256(file_path),
                modified_at=datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            )
        )
    return records


def table_ref(table_name: str) -> str:
    return f"{PROJECT_ID}.{BQ_DATASET}.{table_name}"


def already_processed(file_hash: str) -> bool:
    query = f"""
        SELECT COUNT(1) AS cnt
        FROM `{table_ref('contracts')}`
        WHERE file_hash = @file_hash
          AND extraction_status IN ('COMPLETED', 'ASSESSED', 'LOADED')
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("file_hash", "STRING", file_hash)]
    )
    rows = list(bq_client.query(query, job_config=job_config).result())
    return rows[0].cnt > 0 if rows else False


def upload_file_to_gcs(file_record: FileRecord) -> str:
    bucket = storage_client.bucket(GCS_BUCKET)
    object_name = f"{RAW_PREFIX}/{file_record.file_name}"
    blob = bucket.blob(object_name)
    blob.upload_from_filename(file_record.file_path)
    gcs_uri = f"gs://{GCS_BUCKET}/{object_name}"
    logger.info("Uploaded %s to %s", file_record.file_name, gcs_uri)
    return gcs_uri


def process_document(gcs_input_uri: str) -> documentai.Document:
    processor_name = docai_client.processor_path(PROJECT_ID, LOCATION, PROCESSOR_ID)

    request = documentai.ProcessRequest(
        name=processor_name,
        raw_document=None,
        inline_document=None,
        skip_human_review=True,
        process_options=documentai.ProcessOptions(),
        gcs_document=documentai.GcsDocument(gcs_uri=gcs_input_uri, mime_type="application/pdf"),
    )

    result = docai_client.process_document(request=request)
    logger.info("Document AI processed %s", gcs_input_uri)
    return result.document


def save_docai_json(contract_id: str, document: documentai.Document) -> str:
    bucket = storage_client.bucket(GCS_BUCKET)
    object_name = f"{EXTRACT_PREFIX}/{contract_id}.json"
    blob = bucket.blob(object_name)
    payload = documentai.Document.to_json(document, including_default_value_fields=False)
    blob.upload_from_string(payload, content_type="application/json")
    gcs_uri = f"gs://{GCS_BUCKET}/{object_name}"
    logger.info("Stored Document AI JSON to %s", gcs_uri)
    return gcs_uri


def extract_text(document: documentai.Document) -> str:
    return document.text or ""


def split_into_clauses(text: str) -> List[Dict[str, Any]]:
    """
    Simple clause splitter for the synthetic input pack.
    Splits on headings like '1. Title', '2. Term', etc.
    Replace with richer parsing logic if needed.
    """
    text = re.sub(r"\r\n?", "\n", text)
    pattern = re.compile(r"(?m)^\s*(\d+\.\s+[A-Za-z][^\n]*)\n")
    matches = list(pattern.finditer(text))
    if not matches:
        return [{
            "clause_number": None,
            "clause_title": "Full Document",
            "clause_text": text.strip(),
            "page_number": None,
            "section_name": None,
        }]

    clauses: List[Dict[str, Any]] = []
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        heading = match.group(1).strip()
        clause_no = heading.split(".", 1)[0].strip()
        title = heading.split(".", 1)[1].strip() if "." in heading else heading
        body = text[start:end].strip()
        clauses.append({
            "clause_number": clause_no,
            "clause_title": title,
            "clause_text": body,
            "page_number": None,
            "section_name": title,
        })
    return clauses


def derive_contract_type(file_name: str) -> str:
    base = os.path.splitext(file_name)[0]
    parts = base.split("_")
    # Strip numeric prefix and risk suffix if present
    cleaned = [p for p in parts if not p.isdigit() and p.lower() not in {"high", "medium", "low", "mixed", "risk"}]
    return " ".join(cleaned).replace("  ", " ").strip() or "Unknown"


def load_rows(table_name: str, rows: List[Dict[str, Any]]):
    if not rows:
        return
    errors = bq_client.insert_rows_json(table_ref(table_name), rows)
    if errors:
        raise RuntimeError(f"BigQuery insert errors for {table_name}: {errors}")


def write_audit(contract_id: str, step_name: str, status: str, message: str, batch_id: str):
    row = {
        "event_id": str(uuid.uuid4()),
        "contract_id": contract_id,
        "step_name": step_name,
        "status": status,
        "timestamp": utc_now_iso(),
        "message": message,
        "batch_id": batch_id,
    }
    load_rows("processing_audit", [row])


def process_file(file_record: FileRecord, batch_id: str):
    if already_processed(file_record.sha256):
        logger.info("Skipping duplicate file %s", file_record.file_name)
        return

    contract_id = f"CTR-{uuid.uuid4().hex[:12].upper()}"
    contract_row = {
        "contract_id": contract_id,
        "file_name": file_record.file_name,
        "file_path": file_record.file_path,
        "file_hash": file_record.sha256,
        "file_size_bytes": file_record.file_size_bytes,
        "upload_time": utc_now_iso(),
        "document_type": derive_contract_type(file_record.file_name),
        "extraction_status": "RECEIVED",
        "total_pages": None,
        "extracted_text_uri": None,
        "raw_gcs_uri": None,
        "processing_batch_id": batch_id,
        "source_system": "local_folder",
        "created_at": utc_now_iso(),
    }
    load_rows("contracts", [contract_row])
    write_audit(contract_id, "RECEIVE", "SUCCESS", f"Received {file_record.file_name}", batch_id)

    try:
        gcs_uri = upload_file_to_gcs(file_record)
        write_audit(contract_id, "UPLOAD", "SUCCESS", gcs_uri, batch_id)

        document = process_document(gcs_uri)
        docai_json_uri = save_docai_json(contract_id, document)
        text = extract_text(document)
        clauses = split_into_clauses(text)

        contract_update_query = f"""
        UPDATE `{table_ref('contracts')}`
        SET extraction_status = 'COMPLETED',
            total_pages = @pages,
            extracted_text_uri = @extracted_text_uri,
            raw_gcs_uri = @raw_gcs_uri
        WHERE contract_id = @contract_id
        """
        params = [
            bigquery.ScalarQueryParameter("pages", "INT64", len(document.pages)),
            bigquery.ScalarQueryParameter("extracted_text_uri", "STRING", docai_json_uri),
            bigquery.ScalarQueryParameter("raw_gcs_uri", "STRING", gcs_uri),
            bigquery.ScalarQueryParameter("contract_id", "STRING", contract_id),
        ]
        bq_client.query(contract_update_query, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()

        clause_rows = []
        for idx, c in enumerate(clauses, start=1):
            clause_rows.append({
                "clause_id": f"{contract_id}-CL-{idx:03d}",
                "contract_id": contract_id,
                "clause_number": c["clause_number"],
                "clause_title": c["clause_title"],
                "clause_text": c["clause_text"],
                "page_number": c["page_number"],
                "section_name": c["section_name"],
                "created_at": utc_now_iso(),
            })
        load_rows("contract_clauses", clause_rows)
        write_audit(contract_id, "STRUCTURE", "SUCCESS", f"Generated {len(clause_rows)} clauses", batch_id)
        logger.info("Completed ingestion for %s (%s clauses)", file_record.file_name, len(clause_rows))

    except Exception as exc:
        logger.exception("Failed processing %s", file_record.file_name)
        write_audit(contract_id, "PROCESS", "FAILED", str(exc), batch_id)
        fail_query = f"""
        UPDATE `{table_ref('contracts')}`
        SET extraction_status = 'FAILED'
        WHERE contract_id = @contract_id
        """
        bq_client.query(
            fail_query,
            job_config=bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("contract_id", "STRING", contract_id)]
            ),
        ).result()


def main():
    batch_id = datetime.now(timezone.utc).strftime("BATCH-%Y%m%d-%H%M%S")
    logger.info("Starting batch %s from %s", batch_id, INPUT_FOLDER)
    files = scan_folder(INPUT_FOLDER)
    logger.info("Found %d candidate files", len(files))

    for file_record in files:
        process_file(file_record, batch_id)

    logger.info("Completed batch %s", batch_id)


if __name__ == "__main__":
    main()
