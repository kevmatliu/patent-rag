from __future__ import annotations

from enum import Enum


class ExtractionStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class ValidationStatus(str, Enum):
    UNPROCESSED = "unprocessed"
    VALID = "valid"
    PARSE_FAILED = "parse_failed"
    SANITIZE_FAILED = "sanitize_failed"
    STANDARDIZE_FAILED = "standardize_failed"
