"""
backend/rule_engine/engine.py
──────────────────────────────────────────────────────────────────────────────
RuleEngine: orchestrates all category checkers in parallel via asyncio.gather,
loads civil_checklist.json as the single source of truth for all rules,
and merges results into a single CheckResult.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.rule_engine.checkers.fiscal_checker import FiscalChecker
from backend.rule_engine.checkers.format_checker import FormatChecker
from backend.rule_engine.checkers.structure_checker import StructureChecker
from backend.rule_engine.models import CheckResult, Objection, ParsedDocument

logger = logging.getLogger(__name__)

# Default checklist path relative to the project root (scrutinyai/)
_DEFAULT_CHECKLIST_PATH = (
    Path(__file__).resolve().parents[2] / "rules" / "civil_checklist.json"
)


class RuleEngine:
    """
    Orchestrates FormatChecker, StructureChecker, and FiscalChecker.

    Usage:
        engine = RuleEngine()
        result = await engine.run(parsed_document)
    """

    def __init__(
        self,
        checklist_path: str | Path = _DEFAULT_CHECKLIST_PATH,
    ) -> None:
        """
        Load the checklist JSON and filter points per category.

        Args:
            checklist_path: Path to civil_checklist.json.
                            Defaults to rules/civil_checklist.json relative
                            to the project root.

        Raises:
            FileNotFoundError: If the checklist file does not exist.
            ValueError:         If the JSON is missing required keys.
        """
        self._checklist = self._load_checklist(Path(checklist_path))
        self._checklist_version: str = self._checklist.get("version", "unknown")

        all_points: list[dict[str, Any]] = self._checklist.get("points", [])

        self._format_points = [p for p in all_points if p["category"] == "FORMAT"]
        self._structure_points = [p for p in all_points if p["category"] == "STRUCTURE"]
        self._fiscal_points = [p for p in all_points if p["category"] == "FISCAL"]

        logger.info(
            "RuleEngine loaded checklist v%s: %d FORMAT, %d STRUCTURE, %d FISCAL points.",
            self._checklist_version,
            len(self._format_points),
            len(self._structure_points),
            len(self._fiscal_points),
        )

    def _load_checklist(self, path: Path) -> dict[str, Any]:
        """
        Parse civil_checklist.json and validate required top-level keys.

        Raises:
            FileNotFoundError: If the file is missing.
            ValueError:         If required keys are absent.
        """
        if not path.exists():
            raise FileNotFoundError(
                f"civil_checklist.json not found at: {path}. "
                "Ensure the 'rules/' directory is present in the project root."
            )

        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)

        required_keys = {"version", "points"}
        missing = required_keys - data.keys()
        if missing:
            raise ValueError(
                f"civil_checklist.json is missing required keys: {missing}"
            )

        if not isinstance(data["points"], list):
            raise ValueError("civil_checklist.json 'points' must be a list.")

        return data

    async def run(self, document: ParsedDocument) -> CheckResult:
        """
        Main entry point.

        Runs all three category checkers concurrently via asyncio.gather,
        merges the resulting objections, and returns a single CheckResult.

        Args:
            document: Fully parsed and section-detected document.

        Returns:
            CheckResult with all objections and severity counts populated.
        """
        format_checker = FormatChecker(self._format_points)
        structure_checker = StructureChecker(self._structure_points)
        fiscal_checker = FiscalChecker(self._fiscal_points)

        logger.info(
            "Starting Rule Engine check for file_id=%s, total_pages=%d, ocr=%s",
            document.file_id,
            document.total_pages,
            document.ocr_path_used,
        )

        # Run all three checkers in parallel
        format_objections, structure_objections, fiscal_objections = await asyncio.gather(
            format_checker.check(document),
            structure_checker.check(document),
            fiscal_checker.check(document),
        )

        total_ai_tokens = (
            structure_checker.ai_tokens_used + fiscal_checker.ai_tokens_used
        )

        result = self._merge_results(
            document=document,
            objection_lists=[
                format_objections,
                structure_objections,
                fiscal_objections,
            ],
            ai_tokens=total_ai_tokens,
            checklist_version=self._checklist_version,
        )

        logger.info(
            "Check complete for file_id=%s: %d CRITICAL, %d MAJOR, %d MINOR objections. "
            "AI tokens used: %d.",
            document.file_id,
            result.critical_count,
            result.major_count,
            result.minor_count,
            total_ai_tokens,
        )

        return result

    def _merge_results(
        self,
        document: ParsedDocument,
        objection_lists: list[list[Objection]],
        ai_tokens: int,
        checklist_version: str,
    ) -> CheckResult:
        """
        Flatten objection lists from all checkers into a single CheckResult.

        Ordering: CRITICAL first, then MAJOR, then MINOR.
        Within each severity group, preserve original checker order.
        """
        all_objections: list[Objection] = []
        for objection_list in objection_lists:
            all_objections.extend(objection_list)

        # Sort by severity tier for consistent report ordering
        _order = {"CRITICAL": 0, "MAJOR": 1, "MINOR": 2}
        all_objections.sort(key=lambda o: _order.get(o.severity, 99))

        result = CheckResult(
            document=document,
            objections=all_objections,
            checked_at=datetime.utcnow(),
            checklist_version=checklist_version,
            total_ai_tokens_used=ai_tokens,
        )
        result.compute_counts()

        return result

    # ── Public getters for testing / API use ───────────────────

    @property
    def checklist_version(self) -> str:
        """Return the version string from the loaded checklist."""
        return self._checklist_version

    @property
    def total_checklist_points(self) -> int:
        """Return the total number of checklist points across all categories."""
        return (
            len(self._format_points)
            + len(self._structure_points)
            + len(self._fiscal_points)
        )
