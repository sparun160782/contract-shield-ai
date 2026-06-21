"""
Configuration management for the ADK risk assessment agent.

Loads and validates environment variables for agent operation.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class AgentConfig:
    """Configuration for the risk assessment agent."""

    # GCP settings
    project_id: str
    location: str
    
    # BigQuery settings
    bq_dataset: str
    
    # Model/Agent settings
    model_name: str
    temperature: float
    #max_tokens: int
    
    # Processing settings
    batch_size: int
    query_limit: int
    
    # Output settings
    output_bucket: str

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Load configuration from environment variables."""
        return cls(
            project_id=os.getenv("GCP_PROJECT_ID", "project-05cb579e-230b-4e28-b9b"),
            location=os.getenv("AGENT_LOCATION", "us-central1"),
            bq_dataset=os.getenv("BQ_DATASET", "contract_risk"),
            model_name=os.getenv("MODEL_NAME", "gemini-2.5-flash"),
            temperature=float(os.getenv("MODEL_TEMPERATURE", "0")),
            #max_tokens=int(os.getenv("MODEL_MAX_TOKENS", "1000")),
            batch_size=int(os.getenv("BATCH_SIZE", "10")),
            query_limit=int(os.getenv("QUERY_LIMIT", "100")),
            output_bucket=os.getenv("OUTPUT_BUCKET", "contract-risk-bucket"),
        )

    def validate(self) -> None:
        """Validate configuration parameters."""
        errors = []

        if not self.project_id:
            errors.append("GCP_PROJECT_ID not set")
        if not self.bq_dataset:
            errors.append("BQ_DATASET not set")
        if not self.model_name:
            errors.append("MODEL_NAME not set")
        #if self.temperature < 0 or self.temperature > 1:
        #    errors.append("MODEL_TEMPERATURE must be between 0 and 1")
        #if self.max_tokens < 100:
        #    errors.append("MODEL_MAX_TOKENS must be at least 100")

        if errors:
            raise ValueError(f"Configuration validation failed:\n" + "\n".join(errors))

    def __repr__(self) -> str:
        """Safe representation without sensitive data."""
        return (
            f"AgentConfig(project_id={self.project_id}, "
            f"model={self.model_name}, "
            f"dataset={self.bq_dataset})"
        )
