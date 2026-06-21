"""
File scanning and deduplication module.

Scans local folder for contracts and tracks files by hash to prevent reprocessing.
"""

import os
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List

from src.config import Config

logger = logging.getLogger(__name__)


@dataclass
class FileRecord:
    """Represents a contract file to be processed."""

    file_path: str
    file_name: str
    extension: str
    file_size_bytes: int
    sha256: str
    modified_at: str


class FileScanner:
    """Scans local folder for contracts and deduplicates by hash."""

    def __init__(self, config: Config):
        self.config = config
        self.seen_hashes: set = set()

    @staticmethod
    def _compute_sha256(file_path: str) -> str:
        """Compute SHA-256 hash of file."""
        sha = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha.update(chunk)
        return sha.hexdigest()

    def scan(self) -> List[FileRecord]:
        """Scan folder and return unique files."""
        records: List[FileRecord] = []

        logger.info(f"Scanning folder: {self.config.input_folder}")

        if not os.path.isdir(self.config.input_folder):
            logger.warning(f"Input folder does not exist: {self.config.input_folder}")
            return records

        for entry in sorted(os.listdir(self.config.input_folder)):
            file_path = os.path.join(self.config.input_folder, entry)
            
            if not os.path.isfile(file_path):
                continue

            _, ext = os.path.splitext(entry)
            ext = ext.lower()

            if ext not in self.config.allowed_extensions:
                logger.debug(f"Skipping {entry} (not allowed extension)")
                continue

            try:
                stat = os.stat(file_path)
                sha256 = self._compute_sha256(file_path)

                # Check for duplicates
                if sha256 in self.seen_hashes:
                    logger.info(f"Skipping duplicate: {entry} (hash: {sha256[:8]}...)")
                    continue

                self.seen_hashes.add(sha256)

                record = FileRecord(
                    file_path=file_path,
                    file_name=entry,
                    extension=ext,
                    file_size_bytes=stat.st_size,
                    sha256=sha256,
                    modified_at=datetime.fromtimestamp(
                        stat.st_mtime, timezone.utc
                    ).isoformat(),
                )
                records.append(record)
                logger.info(f"Found: {entry} ({stat.st_size} bytes)")

            except Exception as e:
                logger.error(f"Error scanning {entry}: {e}")

        logger.info(f"Scan complete: {len(records)} unique files found")
        return records
