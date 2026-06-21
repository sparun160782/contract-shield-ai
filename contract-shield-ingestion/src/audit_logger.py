"""
Audit logging module for pipeline traceability.

Tracks all processing steps for compliance and debugging.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from google.cloud import bigquery

from src.config import Config

logger = logging.getLogger(__name__)


class AuditLogger:
    """Logs audit events for pipeline traceability."""

    def __init__(self, config: Config):
        self.config = config
        self.client = bigquery.Client(project=config.project_id)
        self.dataset = self.client.dataset(config.bq_dataset)

    def log(
        self,
        contract_id: str,
        step_name: str,
        status: str,
        message: Optional[str] = None,
        batch_id: Optional[str] = None,
    ) -> None:
        """Log a processing step."""
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
                "message": message or "",
                "batch_id": batch_id or "manual",
            }

            errors = self.client.insert_rows_json(table, [row])

            if errors:
                logger.warning(f"Audit log insert error: {errors}")
            else:
                logger.debug(f"Logged audit event: {step_name} - {status}")

        except Exception as e:
            logger.warning(f"Failed to log audit event: {e}")
