"""
backend/rule_engine/checkers/base_checker.py
──────────────────────────────────────────────────────────────────────────────
Abstract base class for all category checkers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from backend.rule_engine.models import Objection, ParsedDocument


class BaseChecker(ABC):
    """
    Abstract base for FormatChecker, StructureChecker, and FiscalChecker.

    Each subclass receives the subset of checklist points that belongs to
    its category. Points are plain dicts loaded from civil_checklist.json.
    """

    def __init__(self, checklist_points: list[dict[str, Any]]) -> None:
        """
        Store the filtered checklist points for this checker's category.

        Args:
            checklist_points: List of dicts, each matching a single entry
                              from civil_checklist.json["points"] for this
                              checker's category.
        """
        self._points: list[dict[str, Any]] = checklist_points
        self._ai_tokens_used: int = 0

    @abstractmethod
    async def check(self, document: ParsedDocument) -> list[Objection]:
        """
        Execute all assigned checklist points against the document.

        Args:
            document: Fully parsed document with sections and raw text.

        Returns:
            List of Objection objects — may be empty if no violations found.
        """

    @property
    def ai_tokens_used(self) -> int:
        """
        Total Gemini API tokens consumed during this checker's run.
        Always 0 for fully deterministic checkers (FormatChecker).
        """
        return self._ai_tokens_used

    # ── Shared utility ─────────────────────────────────────────

    def _get_section_text(
        self, document: ParsedDocument, section_scope: str
    ) -> str:
        """
        Return the text for a given section_scope value.

        If section_scope is "*", concatenate all raw_text_by_page values.
        If the section is not detected in the document, return "".
        """
        if section_scope == "*":
            pages = sorted(document.raw_text_by_page.keys())
            return "\n".join(document.raw_text_by_page.get(p, "") for p in pages)

        return document.raw_text_by_section.get(section_scope, "")

    def _get_section_pages(
        self, document: ParsedDocument, section_scope: str
    ) -> list[int]:
        """
        Return the list of 1-indexed page numbers for a section.

        If section_scope is "*", return all pages.
        If the section is not found, return [].
        """
        if section_scope == "*":
            return sorted(document.raw_text_by_page.keys())

        span = document.sections.get(section_scope)
        if span is None:
            return []
        start, end = span
        return list(range(start, end + 1))
