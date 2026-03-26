"""
backend/rule_engine/models.py
──────────────────────────────────────────────────────────────────────────────
Core dataclasses for ScrutinyAI.

Dependency order (used by callers):
  Objection → ParsedDocument → CheckResult
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


# ──────────────────────────────────────────────────────────────
# Objection
# ──────────────────────────────────────────────────────────────

@dataclass
class Objection:
    """
    A single objection raised against a civil filing.

    confidence_score ranges from 0.0 (pure guess) to 1.0 (deterministic).
    requires_manual_verification is auto-set True when confidence_score < 0.70.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    category: Literal["FORMAT", "STRUCTURE", "FISCAL"] = "FORMAT"
    severity: Literal["CRITICAL", "MAJOR", "MINOR"] = "MAJOR"

    # Links back to the checklist entry that triggered this objection
    checklist_point_id: str = ""

    # 1-indexed page numbers where the violation was found
    page_references: list[int] = field(default_factory=list)

    # E.g. "Rule 3(1)(a), Karnataka HC Rules 1959"
    rule_citation: str = ""

    # Human-readable description of the problem
    description: str = ""

    # Actionable guidance for the advocate/clerk
    suggested_fix: str = ""

    # 0.0–1.0; deterministic checks always emit 1.0
    confidence_score: float = 1.0

    # True when confidence_score < 0.70 — auto-computed in __post_init__
    requires_manual_verification: bool = False

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence_score <= 1.0:
            raise ValueError(
                f"confidence_score must be 0.0–1.0, got {self.confidence_score!r}"
            )
        # Enforce the 0.70 threshold rule automatically
        self.requires_manual_verification = self.confidence_score < 0.70


# ──────────────────────────────────────────────────────────────
# ParsedDocument
# ──────────────────────────────────────────────────────────────

# Valid section names (single source of truth)
VALID_SECTIONS = frozenset({
    "INDEX",
    "SYNOPSIS",
    "MEMO_OF_PETITION",
    "VERIFYING_AFFIDAVIT",
    "ANNEXURES",
    "VAKALATHNAMA",
})


@dataclass
class ParsedDocument:
    """
    Fully parsed representation of an uploaded PDF, produced by the OCR
    pipeline (PDFParser → SectionDetector) and consumed by RuleEngine.
    """

    # Supabase storage file ID (passed through from the API layer)
    file_id: str = ""

    # SHA-256 hex digest of the raw file bytes — used for deduplication
    file_hash: str = ""

    total_pages: int = 0

    # Which OCR path was taken
    ocr_path_used: Literal["PYMUPDF", "TESSERACT", "GOOGLE_DOCAI"] = "PYMUPDF"

    # section_name → (start_page, end_page) — both 1-indexed, inclusive
    # Only sections that were actually detected are present.
    sections: dict[str, tuple[int, int]] = field(default_factory=dict)

    # section_name → concatenated raw text for that section
    raw_text_by_section: dict[str, str] = field(default_factory=dict)

    # 1-indexed page number → raw text; populated by PDFParser,
    # consumed by SectionDetector to build sections / raw_text_by_section.
    raw_text_by_page: dict[int, str] = field(default_factory=dict)

    # Average OCR confidence across all pages (0.0–1.0).
    # Always 1.0 for text-native PDFs; computed from Tesseract output for scans.
    overall_ocr_confidence: float = 1.0

    # Path to the original PDF file on disk — needed by FormatChecker
    # to open fitz page objects for geometry measurements.
    pdf_file_path: str = ""


# ──────────────────────────────────────────────────────────────
# CheckResult
# ──────────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    """
    Aggregate result returned by RuleEngine.run() after all checkers
    have been executed.
    """

    document: ParsedDocument = field(default_factory=ParsedDocument)
    objections: list[Objection] = field(default_factory=list)

    # UTC timestamp when the check was performed
    checked_at: datetime = field(default_factory=datetime.utcnow)

    # Matches civil_checklist.json → "version"
    checklist_version: str = ""

    # Total Gemini input+output tokens consumed across all AI-assisted checks
    total_ai_tokens_used: int = 0

    # Counts derived from the objections list (call compute_counts() to populate)
    critical_count: int = 0
    major_count: int = 0
    minor_count: int = 0

    def compute_counts(self) -> None:
        """
        Recompute severity counts from the current objections list.
        Must be called after all objections have been appended.
        """
        self.critical_count = sum(
            1 for o in self.objections if o.severity == "CRITICAL"
        )
        self.major_count = sum(
            1 for o in self.objections if o.severity == "MAJOR"
        )
        self.minor_count = sum(
            1 for o in self.objections if o.severity == "MINOR"
        )

    # ── Convenience helpers ────────────────────────────────────

    @property
    def definite_objections(self) -> list[Objection]:
        """Objections with confidence ≥ 0.70 — shown as confirmed errors."""
        return [o for o in self.objections if not o.requires_manual_verification]

    @property
    def manual_review_objections(self) -> list[Objection]:
        """Objections with confidence < 0.70 — shown in 'verify manually' section."""
        return [o for o in self.objections if o.requires_manual_verification]

    def to_dict(self) -> dict:
        """
        Serialise to a plain dict suitable for JSON responses.
        Datetimes are ISO-formatted strings.
        """
        return {
            "file_id": self.document.file_id,
            "file_hash": self.document.file_hash,
            "total_pages": self.document.total_pages,
            "ocr_path_used": self.document.ocr_path_used,
            "overall_ocr_confidence": self.document.overall_ocr_confidence,
            "sections_detected": list(self.document.sections.keys()),
            "checked_at": self.checked_at.isoformat() + "Z",
            "checklist_version": self.checklist_version,
            "total_ai_tokens_used": self.total_ai_tokens_used,
            "critical_count": self.critical_count,
            "major_count": self.major_count,
            "minor_count": self.minor_count,
            "objections": [
                {
                    "id": o.id,
                    "category": o.category,
                    "severity": o.severity,
                    "checklist_point_id": o.checklist_point_id,
                    "page_references": o.page_references,
                    "rule_citation": o.rule_citation,
                    "description": o.description,
                    "suggested_fix": o.suggested_fix,
                    "confidence_score": round(o.confidence_score, 4),
                    "requires_manual_verification": o.requires_manual_verification,
                }
                for o in self.objections
            ],
        }
