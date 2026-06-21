"""
Document processing module for Document AI integration.

Handles uploading contracts to Cloud Storage and processing with Google Document AI.
"""

import logging
from typing import Optional, Dict, Any

from google.cloud import storage
from google.cloud import documentai

from src.config import Config
from src.file_scanner import FileRecord

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Handles Document AI processing and Cloud Storage operations."""

    def __init__(self, config: Config):
        self.config = config
        self.storage_client = storage.Client(project=config.project_id)
        self.docai_client = documentai.DocumentProcessorServiceClient(
            client_options={"api_endpoint": f"{config.location}-documentai.googleapis.com"},
            transport="rest",
        )
        self.bucket = self.storage_client.bucket(config.gcs_bucket)

    @staticmethod
    def _anchor_text(document_text: str, text_anchor: Any) -> str:
        """Safely extract text from a Document AI text anchor."""
        if not text_anchor or not getattr(text_anchor, "text_segments", None):
            return ""

        parts = []
        for seg in text_anchor.text_segments:
            start = int(getattr(seg, "start_index", 0) or 0)
            end = int(getattr(seg, "end_index", 0) or 0)
            if end > start:
                parts.append(document_text[start:end])
        return " ".join(parts).strip()

    def upload_to_gcs(self, file_record: FileRecord, batch_id: str) -> str:
        """Upload contract file to Cloud Storage."""
        try:
            # Create path in bucket: raw-contracts/{batch_id}/{filename}
            blob_path = f"{self.config.raw_prefix}/{batch_id}/{file_record.file_name}"
            blob = self.bucket.blob(blob_path)

            logger.info(f"Uploading to GCS: gs://{self.config.gcs_bucket}/{blob_path}")

            with open(file_record.file_path, "rb") as f:
                blob.upload_from_file(f)

            gcs_uri = f"gs://{self.config.gcs_bucket}/{blob_path}"
            logger.info(f"Upload successful: {gcs_uri}")
            return gcs_uri

        except Exception as e:
            logger.error(f"GCS upload failed for {file_record.file_name}: {e}")
            raise

    def extract_with_docai(self, gcs_uri: str, file_name: str) -> Dict[str, Any]:
        """Process document with Google Document AI for text extraction."""
        try:
            logger.info(f"Submitting to Document AI: {gcs_uri}")

            # Prepare request
            name = self.docai_client.processor_path(
                self.config.project_id, self.config.location, self.config.processor_id
            )

            mime_type = "application/pdf"
            if file_name.lower().endswith(".docx"):
                mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

            # Build request
            request = documentai.ProcessRequest(
                name=name,
                gcs_document=documentai.GcsDocument(gcs_uri=gcs_uri, mime_type=mime_type),
                skip_human_review=True,
            )

            # Process synchronously
            logger.info("Processing document...")
            result = self.docai_client.process_document(request=request)

            extracted_document = result.document
            logger.info(
                f"Document processed: {len(extracted_document.pages)} pages, "
                f"text length: {len(extracted_document.text)} chars"
            )

            # Return structured result
            return {
                "file_name": file_name,
                "gcs_uri": gcs_uri,
                "full_text": extracted_document.text,
                "page_count": len(extracted_document.pages),
                "pages": [
                    {
                        "page_number": page.page_number,
                        "text_anchor_segments": len(page.tokens),
                    }
                    for page in extracted_document.pages
                ],
                "entities": [
                    {
                        "type": entity.type_,
                        "text": self._anchor_text(extracted_document.text or "", entity.text_anchor),
                    }
                    for entity in extracted_document.entities
                ],
            }

        except Exception as e:
            logger.error(f"Document AI processing failed: {e}", exc_info=True)
            raise

    def save_extraction_output(
        self, extraction_result: Dict[str, Any], batch_id: str
    ) -> Optional[str]:
        """Save raw extraction output to GCS for audit trail."""
        try:
            import json

            safe_name = extraction_result["file_name"].replace("/", "_")
            blob_path = f"{self.config.extract_prefix}/{batch_id}/{safe_name}.json"
            blob = self.bucket.blob(blob_path)

            logger.debug(f"Saving extraction output: gs://{self.config.gcs_bucket}/{blob_path}")
            blob.upload_from_string(
                json.dumps(extraction_result, indent=2), content_type="application/json"
            )

            return f"gs://{self.config.gcs_bucket}/{blob_path}"

        except Exception as e:
            logger.warning(f"Failed to save extraction output: {e}")
            return None
