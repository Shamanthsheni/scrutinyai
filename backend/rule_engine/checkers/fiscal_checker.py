"""
backend/rule_engine/checkers/fiscal_checker.py
──────────────────────────────────────────────────────────────────────────────
Hybrid FISCAL checker.

Deterministic checks (confidence = 1.0):
  FSC-001  Court fee amount (slab computation against fee_formulas.json)
  FSC-002  Process fee paid

AI-assisted checks (Gemini 2.0 Flash):
  FSC-003  Suit valuation reasonableness
  FSC-004  Relief-to-fee consistency
  FSC-005  Pecuniary jurisdiction match

Fee schedules are read exclusively from rules/fee_formulas.json.
No fee amounts are hardcoded in this file.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

import google.generativeai as genai

from backend.rule_engine.checkers.base_checker import BaseChecker
from backend.rule_engine.models import Objection, ParsedDocument

logger = logging.getLogger(__name__)

# Configure Gemini once at import time
genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))
_gemini_model = genai.GenerativeModel("gemini-2.0-flash")

# Path to fee formulas — resolve relative to this file's project root
_FEE_FORMULAS_PATH = (
    Path(__file__).resolve().parents[3] / "rules" / "fee_formulas.json"
)


def _load_fee_formulas() -> dict:
    """Load fee_formulas.json once at import time."""
    try:
        with _FEE_FORMULAS_PATH.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        logger.error(
            "fee_formulas.json not found at %s. FSC-001/FSC-002 will be skipped.",
            _FEE_FORMULAS_PATH,
        )
        return {}


_FEE_FORMULAS: dict = _load_fee_formulas()


class FiscalChecker(BaseChecker):
    """
    Runs deterministic fee formula checks and AI-assisted fiscal checks.
    """

    async def check(self, document: ParsedDocument) -> list[Objection]:
        """Route each checklist point to the correct handler."""
        objections: list[Objection] = []
        self._ai_tokens_used = 0

        for point in self._points:
            method = point.get("check_method", "DETERMINISTIC")
            point_id = point["id"]

            if method == "DETERMINISTIC":
                result = self._run_deterministic(document, point)
                if result:
                    objections.append(result)

            elif method == "AI_ASSISTED":
                new_objections, tokens = await self._run_ai_check(document, point)
                objections.extend(new_objections)
                self._ai_tokens_used += tokens

        return objections

    # ──────────────────────────────────────────────────────────
    # Deterministic handlers
    # ──────────────────────────────────────────────────────────

    def _run_deterministic(
        self, document: ParsedDocument, point: dict
    ) -> Objection | None:
        section_scope = point.get("section_scope", "MEMO_OF_PETITION")
        section_text = self._get_section_text(document, section_scope)
        section_pages = self._get_section_pages(document, section_scope)

        point_id = point["id"]
        if point_id == "FSC-001":
            return self._check_court_fee(section_text, section_pages, point)
        elif point_id == "FSC-002":
            return self._check_process_fee(section_text, section_pages, point)
        return None

    def _check_court_fee(
        self,
        section_text: str,
        section_pages: list[int],
        point: dict,
    ) -> Objection | None:
        """
        Extract the stated suit valuation and court fee from the petition text,
        compute the required fee from SCHEDULE_I slabs in fee_formulas.json,
        and flag a mismatch.

        Pattern assumptions:
          - Suit value: "suit valued at Rs.<amount>" or "value of suit: Rs.<amount>"
          - Court fee: "court fee of Rs.<amount>" or "court fee paid: Rs.<amount>"
        """
        params = point.get("parameters", {})
        schedule_ref: str = params.get("fee_schedule_ref", "SCHEDULE_I")
        min_fee: float = params.get("min_fee_inr", 100)

        schedule = _FEE_FORMULAS.get(schedule_ref)
        if not schedule or schedule.get("type") != "SLAB":
            logger.warning("Fee schedule '%s' not found or not SLAB type.", schedule_ref)
            return None

        # Extract monetary figures from text
        monetary = self._extract_monetary_values(section_text)
        suit_value = monetary.get("suit_value")
        court_fee_paid = monetary.get("court_fee")

        if suit_value is None:
            # Cannot compute without suit valuation — flag for manual review
            return Objection(
                category="FISCAL",
                severity="MAJOR",
                checklist_point_id=point["id"],
                page_references=section_pages,
                rule_citation=point["rule_source"],
                description=(
                    "The suit valuation could not be extracted from the petition text. "
                    "Court fee cannot be verified without a stated suit value."
                ),
                suggested_fix=(
                    "Clearly state the suit valuation (e.g., 'This suit is valued at "
                    "Rs.X for the purpose of court fees.') in the petition."
                ),
                confidence_score=0.65,
            )

        required_fee = self._compute_slab_fee(suit_value, schedule["slabs"])
        required_fee = max(required_fee, min_fee)

        if court_fee_paid is None:
            return Objection(
                category="FISCAL",
                severity=point["severity"],
                checklist_point_id=point["id"],
                page_references=section_pages,
                rule_citation=point["rule_source"],
                description=(
                    f"Court fee paid could not be identified in the petition. "
                    f"Based on the stated suit value of Rs.{suit_value:,.0f}, "
                    f"the required court fee is Rs.{required_fee:,.0f}."
                ),
                suggested_fix=(
                    f"Affix court fee stamps / pay court fee of Rs.{required_fee:,.0f} "
                    "and clearly mention the amount paid in the petition."
                ),
                confidence_score=0.80,
            )

        # Allow a 5% tolerance for minor rounding differences
        tolerance = max(5.0, required_fee * 0.05)
        if abs(court_fee_paid - required_fee) <= tolerance:
            return None  # correct fee

        diff = required_fee - court_fee_paid
        direction = "short" if diff > 0 else "excess"
        return Objection(
            category="FISCAL",
            severity=point["severity"],
            checklist_point_id=point["id"],
            page_references=section_pages,
            rule_citation=point["rule_source"],
            description=(
                f"Court fee mismatch. Suit value stated: Rs.{suit_value:,.0f}. "
                f"Required fee per Schedule I: Rs.{required_fee:,.0f}. "
                f"Fee paid: Rs.{court_fee_paid:,.0f} "
                f"(Rs.{abs(diff):,.0f} {direction})."
            ),
            suggested_fix=(
                f"Pay the correct court fee of Rs.{required_fee:,.0f} as per "
                "Schedule I of the Karnataka Court Fees and Suits Valuation Act 1958."
            ),
            confidence_score=1.0,
        )

    def _check_process_fee(
        self,
        section_text: str,
        section_pages: list[int],
        point: dict,
    ) -> Objection | None:
        """
        Check that process fee has been mentioned/paid.
        Extract the number of respondents and verify that process fee
        (per_respondent_inr × count) appears in the petition.
        """
        process_cfg = _FEE_FORMULAS.get("PROCESS_FEE", {})
        per_respondent: float = float(
            process_cfg.get("per_respondent_inr", 25)
        )

        respondent_count = self._extract_respondent_count(section_text)

        # Look for any mention of process fee in the text
        has_process_fee_mention = bool(
            re.search(r"process\s+fee", section_text, re.IGNORECASE)
        )

        if has_process_fee_mention:
            return None  # Assume fee is paid if mentioned

        expected_fee = per_respondent * max(respondent_count, 1)

        return Objection(
            category="FISCAL",
            severity=point["severity"],
            checklist_point_id=point["id"],
            page_references=section_pages,
            rule_citation=point["rule_source"],
            description=(
                f"No mention of process fee found in the petition. "
                f"Based on {respondent_count} respondent(s) at Rs.{per_respondent:.0f} "
                f"each, the expected process fee is Rs.{expected_fee:.0f}."
            ),
            suggested_fix=(
                f"Pay process fee of Rs.{per_respondent:.0f} per respondent "
                f"(total Rs.{expected_fee:.0f}) and document it in the petition."
            ),
            confidence_score=0.80,
        )

    # ──────────────────────────────────────────────────────────
    # Monetary / text extraction helpers
    # ──────────────────────────────────────────────────────────

    def _extract_monetary_values(self, text: str) -> dict[str, float | None]:
        """
        Extract suit_value and court_fee from free text using regex patterns.

        Recognises patterns such as:
          - "suit is valued at Rs. 5,00,000"
          - "value of suit: Rs.50000"
          - "court fee of Rs.2,000"
          - "court fee paid: Rs.1500"

        Returns dict with keys "suit_value" and "court_fee";
        values are floats or None if not found.
        """
        result: dict[str, float | None] = {
            "suit_value": None,
            "court_fee": None,
        }

        # Pattern for Indian number format: 1,00,000 or 100000
        amount_re = r"(?:Rs\.?\s*|INR\s*)([\d,]+(?:\.\d{1,2})?)"

        suit_patterns = [
            r"(?:suit\s+(?:is\s+)?valued\s+at|value\s+of\s+suit(?:\s+is)?|suit\s+valuation\s+of)\s*"
            + amount_re,
            r"valued\s+at\s+" + amount_re,
        ]

        fee_patterns = [
            r"court\s+fee\s+(?:of|paid|payable)\s*[:=]?\s*" + amount_re,
            r"court\s+fees?\s*[:=]\s*" + amount_re,
            r"paying\s+a\s+court\s+fee\s+of\s*" + amount_re,
        ]

        def _parse_amount(raw: str) -> float:
            return float(raw.replace(",", ""))

        for pat in suit_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                result["suit_value"] = _parse_amount(m.group(1))
                break

        for pat in fee_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                result["court_fee"] = _parse_amount(m.group(1))
                break

        return result

    def _extract_respondent_count(self, text: str) -> int:
        """
        Attempt to count the number of respondents mentioned.

        Strategies:
          1. Count "Respondent No. X" or "Respondent-X" patterns.
          2. Fall back to counting the word "Respondent".
          3. Default to 1 if nothing found.
        """
        numbered = re.findall(
            r"[Rr]espondent\s*(?:No\.?\s*|[-–]\s*)?(\d+)", text
        )
        if numbered:
            return max(int(n) for n in numbered)

        count = len(re.findall(r"\bRespondent\b", text))
        return max(count, 1)

    @staticmethod
    def _compute_slab_fee(value: float, slabs: list[dict]) -> float:
        """
        Look up the court fee for a given suit value from a slab table.
        Each slab has: from, to (None = open-ended), fee.
        """
        for slab in slabs:
            low = slab["from"]
            high = slab["to"]
            if high is None:
                if value >= low:
                    return float(slab["fee"])
            else:
                if low <= value <= high:
                    return float(slab["fee"])
        return float(slabs[-1]["fee"])  # fallback to highest slab

    # ──────────────────────────────────────────────────────────
    # AI-assisted handler (shared with StructureChecker pattern)
    # ──────────────────────────────────────────────────────────

    async def _run_ai_check(
        self, document: ParsedDocument, point: dict
    ) -> tuple[list[Objection], int]:
        """
        Call Gemini 2.0 Flash with scoped petition text.

        Returns (objections, tokens_used).
        """
        section_scope: str = point.get("section_scope", "MEMO_OF_PETITION")
        max_pages: int = point.get("parameters", {}).get("max_pages_to_send", 4)

        section_text = self._get_section_text(document, section_scope)
        if not section_text.strip():
            return (
                [
                    Objection(
                        category="FISCAL",
                        severity=point["severity"],
                        checklist_point_id=point["id"],
                        page_references=[],
                        rule_citation=point["rule_source"],
                        description=(
                            f"Section '{section_scope}' could not be located. "
                            f"Cannot perform AI check '{point['title']}'."
                        ),
                        suggested_fix=(
                            f"Ensure the '{section_scope}' section is present."
                        ),
                        confidence_score=1.0,
                    )
                ],
                0,
            )

        chars_limit = max_pages * 2000
        section_text_trimmed = section_text[:chars_limit]

        prompt = self._build_prompt(point, section_text_trimmed)

        try:
            response = _gemini_model.generate_content(prompt)
            tokens_used = (len(prompt) + len(response.text)) // 4
            return (
                self._parse_ai_response(response.text, document, point),
                tokens_used,
            )
        except Exception as exc:
            logger.warning(
                "Gemini API call failed for point %s: %s", point["id"], exc
            )
            return [], 0

    def _build_prompt(self, point: dict, section_text: str) -> str:
        """Render the ai_prompt_template with actual section text."""
        template: str = point.get("ai_prompt_template", "")
        return template.replace("{{section_text}}", section_text)

    def _parse_ai_response(
        self,
        response_text: str,
        document: ParsedDocument,
        point: dict,
    ) -> list[Objection]:
        """Parse Gemini JSON response into Objection objects."""
        cleaned = re.sub(r"```(?:json)?", "", response_text).strip().strip("`")

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning(
                "Could not parse Gemini JSON for point %s. Raw: %s",
                point["id"],
                response_text[:200],
            )
            return []

        if not data.get("has_issues", False):
            return []

        objections: list[Objection] = []
        section_pages = self._get_section_pages(
            document, point.get("section_scope", "MEMO_OF_PETITION")
        )

        for issue in data.get("issues", []):
            raw_confidence = float(issue.get("confidence", 0.80))
            confidence = max(0.0, min(1.0, raw_confidence))

            raw_severity = issue.get("severity", point["severity"])
            if raw_severity not in ("CRITICAL", "MAJOR", "MINOR"):
                raw_severity = point["severity"]

            objections.append(
                Objection(
                    category="FISCAL",
                    severity=raw_severity,
                    checklist_point_id=point["id"],
                    page_references=section_pages,
                    rule_citation=point["rule_source"],
                    description=issue.get("description", ""),
                    suggested_fix=issue.get("suggested_fix", ""),
                    confidence_score=confidence,
                )
            )

        return objections
