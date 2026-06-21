"""
Clause normalization and segmentation module.

Extracts and normalizes clauses from raw Document AI output.
"""

import re
import logging
import uuid
from typing import Dict, Any, List
from dataclasses import dataclass

from src.config import Config
from src.file_scanner import FileRecord

logger = logging.getLogger(__name__)


@dataclass
class Clause:
    """Represents a normalized contract clause."""

    clause_id: str
    contract_id: str
    clause_number: str
    clause_title: str
    clause_text: str
    page_number: int
    section_name: str


class ClauseNormalizer:
    """Extracts and normalizes clauses from extracted document text."""

    def __init__(self, config: Config):
        self.config = config

    def extract_clauses(
        self, extraction_result: Dict[str, Any], contract_id: str, file_record: FileRecord
    ) -> List[Clause]:
        """Extract clauses from Document AI output."""
        clauses: List[Clause] = []

        try:
            full_text = extraction_result.get("full_text", "")

            if not full_text or len(full_text) < 100:
                logger.warning(f"Insufficient text extracted from {file_record.file_name}")
                return clauses

            # Simple segmentation: split on numbered sections or common clause markers
            segments = self._segment_text(full_text)

            logger.info(f"Extracted {len(segments)} segments from {file_record.file_name}")

            for idx, segment in enumerate(segments, 1):
                if len(segment["text"].strip()) < 20:
                    continue

                clause = Clause(
                    clause_id=f"{contract_id}-CL-{idx:03d}",
                    contract_id=contract_id,
                    clause_number=str(idx),
                    clause_title=segment.get("title", f"Section {idx}"),
                    clause_text=segment["text"],
                    page_number=segment.get("page_number", 1),
                    section_name=segment.get("section", "General"),
                )
                clauses.append(clause)

            logger.info(f"Normalized {len(clauses)} clauses from {file_record.file_name}")
            return clauses

        except Exception as e:
            logger.error(f"Clause extraction failed: {e}")
            return clauses

    @staticmethod
    def _segment_text(text: str) -> List[Dict[str, Any]]:
        """Segment text into logical sections/clauses."""
        segments = []

        # Split by common section markers
        # Pattern: Numbers, dots, or bullets followed by titles
        pattern = r"^(\d+\.?|\d+\)|-|\*)\s+(.+?)$"

        lines = text.split("\n")
        current_segment = {"title": "", "text": "", "page_number": 1}

        for line in lines:
            line = line.strip()
            if not line:
                continue

            match = re.match(pattern, line)
            if match:
                # Save previous segment if it has content
                if current_segment["text"].strip():
                    segments.append(current_segment)

                # Start new segment
                current_segment = {
                    "title": line[:100],  # Limit title length
                    "text": line,
                    "page_number": 1,
                    "section": "General",
                }
            else:
                # Add to current segment
                if current_segment["text"]:
                    current_segment["text"] += " " + line
                else:
                    current_segment["text"] = line

        # Don't forget last segment
        if current_segment["text"].strip():
            segments.append(current_segment)

        # If no segments found, create one from entire text
        if not segments:
            segments = [
                {
                    "title": "Full Document",
                    "text": text,
                    "page_number": 1,
                    "section": "General",
                }
            ]

        return segments
