"""
Core ingestion pipeline for Contract Shield AI.

This module orchestrates the contract ingestion flow:
1. Scan local folder for contracts
2. Dedup by SHA-256 hash
3. Upload to Cloud Storage
4. Process with Document AI
5. Extract and normalize clauses
6. Load into BigQuery
"""

from __future__ import annotations

import os
import sys
import logging
from typing import Optional
from datetime import datetime, timezone

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import Config
from src.file_scanner import FileScanner
from src.document_processor import DocumentProcessor
from src.clause_normalizer import ClauseNormalizer
from src.bigquery_loader import BigQueryLoader
from src.audit_logger import AuditLogger
from src.network_trust import configure_system_trust

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Main orchestrator for contract ingestion."""

    def __init__(self, config: Config):
        self.config = config
        self.file_scanner = FileScanner(config)
        self.doc_processor = DocumentProcessor(config)
        self.clause_normalizer = ClauseNormalizer(config)
        self.bq_loader = BigQueryLoader(config)
        self.audit_logger = AuditLogger(config)
        self.batch_id = self._generate_batch_id()

    @staticmethod
    def _generate_batch_id() -> str:
        """Generate unique batch identifier."""
        return datetime.now(timezone.utc).strftime("batch-%Y%m%d-%H%M%S")

    def run(self) -> dict:
        """Execute complete ingestion pipeline."""
        logger.info(f"Starting ingestion pipeline (batch: {self.batch_id})")
        results = {
            "batch_id": self.batch_id,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "files_scanned": 0,
            "files_uploaded": 0,
            "files_processed": 0,
            "clauses_extracted": 0,
            "errors": [],
        }

        try:
            # Step 1: Scan local folder
            logger.info(f"Scanning {self.config.input_folder}...")
            file_records = self.file_scanner.scan()
            results["files_scanned"] = len(file_records)
            logger.info(f"Found {len(file_records)} contracts")

            if not file_records:
                logger.warning("No contracts found to process")
                return results

            # Step 2: Upload unique files to GCS
            logger.info("Uploading contracts to Cloud Storage...")
            uploaded_files = []
            for record in file_records:
                try:
                    if self.bq_loader.is_already_processed(record.sha256):
                        logger.info(f"Skipping duplicate already in BigQuery: {record.file_name}")
                        continue

                    gcs_uri = self.doc_processor.upload_to_gcs(record, self.batch_id)
                    uploaded_files.append((record, gcs_uri))
                    results["files_uploaded"] += 1
                except Exception as e:
                    logger.error(f"Upload failed for {record.file_name}: {e}")
                    results["errors"].append(
                        {"file": record.file_name, "step": "upload", "error": str(e)}
                    )

            # Step 3: Process with Document AI
            logger.info("Processing with Document AI...")
            for record, gcs_uri in uploaded_files:
                try:
                    extraction_result = self.doc_processor.extract_with_docai(
                        gcs_uri, record.file_name
                    )
                    extracted_text_uri = self.doc_processor.save_extraction_output(
                        extraction_result, self.batch_id
                    )
                    
                    # Store contract metadata
                    contract_id = self.bq_loader.create_contract(
                        record,
                        gcs_uri,
                        extracted_text_uri or gcs_uri,
                        extraction_result,
                        self.batch_id,
                    )
                    logger.info(f"Created contract record: {contract_id}")
                    results["files_processed"] += 1

                    # Step 4: Normalize and extract clauses
                    logger.info(f"Extracting clauses from {record.file_name}...")
                    clauses = self.clause_normalizer.extract_clauses(
                        extraction_result, contract_id, record
                    )
                    
                    # Step 5: Load clauses to BigQuery
                    self.bq_loader.load_clauses(clauses)
                    results["clauses_extracted"] += len(clauses)
                    logger.info(f"Extracted and stored {len(clauses)} clauses")

                    # Audit
                    self.audit_logger.log(
                        contract_id,
                        "extraction",
                        "completed",
                        f"Extracted {len(clauses)} clauses",
                        self.batch_id,
                    )

                except Exception as e:
                    logger.error(f"Processing failed for {record.file_name}: {e}")
                    results["errors"].append(
                        {
                            "file": record.file_name,
                            "step": "docai_extraction",
                            "error": str(e),
                        }
                    )

        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            results["errors"].append({"step": "pipeline", "error": str(e)})

        results["end_time"] = datetime.now(timezone.utc).isoformat()
        logger.info(f"Pipeline completed: {results['files_processed']} processed, {len(results['errors'])} errors")
        
        return results


def main():
    """Entry point for ingestion pipeline."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    configure_system_trust()

    config = Config.from_env()
    config.validate()

    pipeline = IngestionPipeline(config)
    results = pipeline.run()

    # Print summary
    print("\n" + "=" * 60)
    print("INGESTION PIPELINE SUMMARY")
    print("=" * 60)
    print(f"Batch ID:          {results['batch_id']}")
    print(f"Files Scanned:     {results['files_scanned']}")
    print(f"Files Uploaded:    {results['files_uploaded']}")
    print(f"Files Processed:   {results['files_processed']}")
    print(f"Clauses Extracted: {results['clauses_extracted']}")
    print(f"Errors:            {len(results['errors'])}")
    if results["errors"]:
        print("\nErrors:")
        for error in results["errors"]:
            print(f"  - {error}")
    print("=" * 60)

    # Exit with error code if there were failures
    sys.exit(0 if len(results["errors"]) == 0 else 1)


if __name__ == "__main__":
    main()
