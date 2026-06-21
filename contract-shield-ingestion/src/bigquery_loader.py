"""
BigQuery data loading module.

Handles loading contract metadata, clauses, and audit records into BigQuery.
"""

import logging
import uuid
from typing import Dict, Any, List
from datetime import datetime, timezone

from google.cloud import bigquery
from google.cloud.exceptions import GoogleCloudError

from src.config import Config
from src.file_scanner import FileRecord
from src.clause_normalizer import Clause

logger = logging.getLogger(__name__)


class BigQueryLoader:
    """Loads data into BigQuery tables."""

    def __init__(self, config: Config):
        self.config = config
        self.client = bigquery.Client(project=config.project_id)
        self.dataset = self.client.dataset(config.bq_dataset)

    def create_contract(
        self,
        file_record: FileRecord,
        raw_gcs_uri: str,
        extracted_text_uri: str,
        extraction_result: Dict[str, Any],
        batch_id: str,
    ) -> str:
        """Create contract record in BigQuery."""
        try:
            contract_id = f"CTR-{uuid.uuid4().hex[:12].upper()}"

            table = self.client.get_table(
                self.dataset.table("contracts")
            )

            row = {
                "contract_id": contract_id,
                "file_name": file_record.file_name,
                "file_path": file_record.file_path,
                "file_hash": file_record.sha256,
                "file_size_bytes": file_record.file_size_bytes,
                "upload_time": datetime.now(timezone.utc).isoformat(),
                "document_type": file_record.extension.strip("."),
                "extraction_status": "COMPLETED",
                "total_pages": extraction_result.get("page_count", len(extraction_result.get("pages", []))),
                "extracted_text_uri": extracted_text_uri,
                "raw_gcs_uri": raw_gcs_uri,
                "processing_batch_id": batch_id,
                "source_system": "local_folder",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

            errors = self.client.insert_rows_json(table, [row])

            if errors:
                logger.error(f"BigQuery insert errors: {errors}")
                raise Exception(f"Failed to insert contract: {errors}")

            logger.info(f"Created contract record: {contract_id}")
            return contract_id

        except Exception as e:
            logger.error(f"Failed to create contract record: {e}")
            raise

    def is_already_processed(self, file_hash: str) -> bool:
        """Check whether a file hash has already been processed successfully."""
        query = f"""
        SELECT COUNT(1) AS cnt
        FROM `{self.config.project_id}.{self.config.bq_dataset}.contracts`
        WHERE file_hash = @file_hash
          AND extraction_status IN ('COMPLETED', 'ASSESSED', 'LOADED')
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("file_hash", "STRING", file_hash),
            ]
        )
        rows = list(self.client.query(query, job_config=job_config).result())
        return bool(rows and rows[0]["cnt"] > 0)

    def load_clauses(self, clauses: List[Clause]) -> int:
        """Load clause records into BigQuery."""
        if not clauses:
            return 0

        try:
            table = self.client.get_table(
                self.dataset.table("contract_clauses")
            )

            rows = [
                {
                    "clause_id": clause.clause_id,
                    "contract_id": clause.contract_id,
                    "clause_number": clause.clause_number,
                    "clause_title": clause.clause_title,
                    "clause_text": clause.clause_text,
                    "page_number": clause.page_number,
                    "section_name": clause.section_name,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                for clause in clauses
            ]

            errors = self.client.insert_rows_json(table, rows)

            if errors:
                logger.error(f"BigQuery insert errors: {errors}")
                raise Exception(f"Failed to insert clauses: {errors}")

            logger.info(f"Loaded {len(clauses)} clauses to BigQuery")
            return len(clauses)

        except Exception as e:
            logger.error(f"Failed to load clauses: {e}")
            raise

    def log_audit(
        self,
        contract_id: str,
        step_name: str,
        status: str,
        message: str,
        batch_id: str,
    ) -> None:
        """Log processing step to audit table."""
        try:
            table = self.client.get_table(
                self.dataset.table("processing_audit")
            )

            row = {
                "event_id": f"EVT-{uuid.uuid4().hex[:12].upper()}",
                "contract_id": contract_id,
                "step_name": step_name,
                "status": status,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": message,
                "batch_id": batch_id,
            }

            errors = self.client.insert_rows_json(table, [row])

            if errors:
                logger.warning(f"Failed to log audit: {errors}")

        except Exception as e:
            logger.warning(f"Audit logging error: {e}")
