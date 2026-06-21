"""
Configuration management for the ingestion pipeline.

Loads and validates environment variables and configuration parameters.
"""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv


@dataclass
class Config:
    """Centralized configuration for ingestion pipeline."""

    # GCP settings
    project_id: str
    location: str
    processor_id: str
    
    # Cloud Storage settings
    gcs_bucket: str
    raw_prefix: str
    extract_prefix: str
    
    # BigQuery settings
    bq_dataset: str
    
    # Local paths
    input_folder: str
    
    # Processing
    allowed_extensions: set
    docai_timeout: int
    batch_size: int

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        ingestion_root = Path(__file__).resolve().parents[1]
        repo_root = ingestion_root.parent

        # Load local env files if present (ingestion-scoped first, then repo-level).
        load_dotenv(ingestion_root / ".env.local", override=False)
        load_dotenv(repo_root / ".env.local", override=False)

        input_folder = (os.getenv("INPUT_FOLDER", "../contract_input_pack") or "").strip()
        input_path = Path(input_folder)
        if not input_path.is_absolute():
            input_path = (ingestion_root / input_path).resolve()

        return cls(
            project_id=os.getenv("GCP_PROJECT_ID", "project-05cb579e-230b-4e28-b9b"),
            location=os.getenv("DOCAI_LOCATION", "us"),
            processor_id=os.getenv("DOCAI_PROCESSOR_ID", ""),
            gcs_bucket=os.getenv("GCS_BUCKET", "contract-risk-bucket"),
            raw_prefix=os.getenv("GCS_RAW_PREFIX", "raw-contracts"),
            extract_prefix=os.getenv("GCS_EXTRACT_PREFIX", "docai-output"),
            bq_dataset=os.getenv("BQ_DATASET", "contract_risk"),
            input_folder=str(input_path),
            allowed_extensions={
                ext.strip().lower()
                for ext in os.getenv("ALLOWED_EXTENSIONS", ".pdf").split(",")
                if ext.strip()
            },
            docai_timeout=int(os.getenv("DOCAI_TIMEOUT", "600")),
            batch_size=int(os.getenv("BATCH_SIZE", "5")),
        )

    def validate(self) -> None:
        """Validate configuration parameters."""
        errors = []

        if not self.project_id:
            errors.append("GCP_PROJECT_ID not set")
        if not self.processor_id:
            errors.append("DOCAI_PROCESSOR_ID not set")
        if not self.gcs_bucket:
            errors.append("GCS_BUCKET not set")
        if not self.bq_dataset:
            errors.append("BQ_DATASET not set")
        if not os.path.isdir(self.input_folder):
            errors.append(f"INPUT_FOLDER '{self.input_folder}' does not exist")

        if errors:
            raise ValueError(f"Configuration validation failed:\n" + "\n".join(errors))

    def __repr__(self) -> str:
        """Safe representation without sensitive data."""
        return (
            f"Config(project_id={self.project_id}, "
            f"dataset={self.bq_dataset}, "
            f"input_folder={self.input_folder})"
        )
