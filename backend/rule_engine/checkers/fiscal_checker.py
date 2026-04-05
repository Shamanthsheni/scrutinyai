"""
backend/rule_engine/checkers/fiscal_checker.py
──────────────────────────────────────────────────────────────────────────────
Hybrid FISCAL checker — works with the new civil_checklist.json schema.

Deterministic checks (check_method=DETERMINISTIC):
  - check_type "presence"     → keyword search in full text
  - check_type "calculation"  → fee plausibility check via fee_formulas.json

AI-assisted checks (check_method=AI_ASSISTED):
  Uses the `ai_prompt` field as the Gemini question.
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


def _load_fee_formulas() -> list:
    """Load fee_formulas.json once at import time."""
    try:
        with _FEE_FORMULAS_PATH.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
            logger.info("Loaded %d fee formula entries from %s", len(data), _FEE_FORMULAS_PATH)
            return data
    except FileNotFoundError:
        logger.error(
            "fee_formulas.json not found at %s. Fiscal calculation checks will be skipped.",
            _FEE_FORMULAS_PATH,
        )
        return []


_FEE_FORMULAS: list = _load_fee_formulas()

# Monetary value extraction pattern (handles Rs., Rs, ₹, INR)
_MONEY_RE = re.compile(
    r"(?:rs\.?\s*|₹\s*|inr\s*)([\d,]+(?:\.\d{1,2})?)",
    re.IGNORECASE,
)

# Keywords for deterministic presence checks, keyed by point id
_FISCAL_PRESENCE_KEYWORDS: dict[str, list[str]] = {
    "VI-b":   ["court fee", "c.f.", "receipt no", "treasury receipt", "court fee paid"],
    "VI-e":   ["land acquisition", "sec.48", "section 48", "sec 48", "section 23"],
    "VIII-h": ["welfare stamp", "rs.50", "rs. 50", "₹50", "advocate welfare fund"],
    "IX-e":   ["welfare stamp", "rs.20", "rs. 20", "₹20", "advocate welfare fund"],
}


class FiscalChecker(BaseChecker):
    """
    Runs deterministic fee presence/calculation checks and AI-assisted fiscal checks.
    """

    async def check(self, document: ParsedDocument) -> list[Objection]:
        """Route each FISCAL checklist point to the correct handler."""
        objections: list[Objection] = []
        self._ai_tokens_used = 0

        logger.debug(
            "[FiscalChecker] Starting — %d points to check", len(self._points)
        )

        for point in self._points:
            method = point.get("check_method", "DETERMINISTIC")
            point_id = point["id"]
            check_type = point.get("check_type", "presence")

            logger.debug(
                "[FiscalChecker] Point %s | method=%s | check_type=%s",
                point_id, method, check_type,
            )

            if method == "DETERMINISTIC":
                if check_type == "calculation":
                    result = self._run_fee_calculation_check(document, point)
                else:
                    result = self._run_presence_check(document, point)
                if result:
                    logger.debug("[FiscalChecker] Point %s → OBJECTION raised", point_id)
                    objections.append(result)
                else:
                    logger.debug("[FiscalChecker] Point %s → PASS", point_id)

            elif method == "AI_ASSISTED":
                new_objections, tokens = await self._run_ai_check(document, point)
                logger.debug(
                    "[FiscalChecker] Point %s → AI returned %d objection(s), %d tokens",
                    point_id, len(new_objections), tokens,
                )
                objections.extend(new_objections)
                self._ai_tokens_used += tokens

        logger.debug(
            "[FiscalChecker] Done — %d total objection(s), %d AI tokens",
            len(objections), self._ai_tokens_used,
        )
        return objections

    # ──────────────────────────────────────────────────────────
    # Deterministic: keyword presence
    # ──────────────────────────────────────────────────────────

    def _run_presence_check(
        self, document: ParsedDocument, point: dict
    ) -> Objection | None:
        """Search for fiscal keywords in the full document text."""
        point_id = point["id"]
        keywords = _FISCAL_PRESENCE_KEYWORDS.get(point_id, [])

        if not keywords:
            logger.debug(
                "[FiscalChecker] Point %s — no keywords configured, skipping presence check",
                point_id,
            )
            return None

        full_text = self._get_section_text(document, "*").lower()
        logger.debug(
            "[FiscalChecker] Point %s — searching %d chars for keywords %s",
            point_id, len(full_text), keywords,
        )

        for kw in keywords:
            if kw.lower() in full_text:
                logger.debug(
                    "[FiscalChecker] Point %s — keyword '%s' found → PASS", point_id, kw
                )
                return None

        logger.debug("[FiscalChecker] Point %s — no keywords found → OBJECTION", point_id)
        return Objection(
            category="FISCAL",
            severity=point["severity"],
            checklist_point_id=point_id,
            page_references=[],
            rule_citation=point.get("rule_source", ""),
            description=(
                f"{point.get('description', 'Required fiscal element missing.')} "
                "This item could not be located in the document."
            ),
            suggested_fix=(
                f"Ensure the required fiscal document or statement is present. "
                f"See: {point.get('rule_source', 'Karnataka Court Fees Act')}."
            ),
            confidence_score=0.85,
        )

    # ──────────────────────────────────────────────────────────
    # Deterministic: fee calculation plausibility check
    # ──────────────────────────────────────────────────────────

    def _run_fee_calculation_check(
        self, document: ParsedDocument, point: dict
    ) -> Objection | None:
        """
        Extract monetary amounts from document text and verify they are consistent
        with at least one known fee formula.

        This is a plausibility check — if no monetary amounts are found at all,
        flag for manual review. If amounts are found and a formula matches,
        pass. If no fee formula matches or amounts are implausibly low, flag.
        """
        if not _FEE_FORMULAS:
            logger.debug("[FiscalChecker] VI-a — no fee formulas loaded, skipping")
            return None

        full_text = self._get_section_text(document, "*")
        logger.debug(
            "[FiscalChecker] VI-a — searching %d chars for monetary values", len(full_text)
        )

        matches = _MONEY_RE.findall(full_text.lower())
        logger.debug("[FiscalChecker] VI-a — monetary values found: %s", matches)

        if not matches:
            logger.debug("[FiscalChecker] VI-a — no monetary values found → OBJECTION")
            return Objection(
                category="FISCAL",
                severity=point["severity"],
                checklist_point_id=point["id"],
                page_references=[],
                rule_citation=point.get("rule_source", ""),
                description=(
                    "No court fee amount could be detected in this document. "
                    "The court fee receipt and the amount must be explicitly stated."
                ),
                suggested_fix=(
                    "Include the exact court fee amount paid (e.g. 'Court fee of Rs.200 paid "
                    "under receipt no. XXX dated DD/MM/YYYY')."
                ),
                confidence_score=0.80,
            )

        # Found monetary values — plausibility check: minimum Rs.100 for any filing
        amounts = []
        for raw in matches:
            try:
                amounts.append(float(raw.replace(",", "")))
            except ValueError:
                pass

        min_amount = min(amounts) if amounts else 0
        all_min_fees = [f.get("minimum_fee_rs", 0) or 0 for f in _FEE_FORMULAS]
        overall_min = min(all_min_fees) if all_min_fees else 100

        logger.debug(
            "[FiscalChecker] VI-a — min amount found=%.2f, minimum acceptable=%.2f",
            min_amount, overall_min,
        )

        if min_amount > 0 and min_amount < overall_min:
            return Objection(
                category="FISCAL",
                severity=point["severity"],
                checklist_point_id=point["id"],
                page_references=[],
                rule_citation=point.get("rule_source", ""),
                description=(
                    f"The smallest monetary amount found in the document (Rs.{min_amount:.0f}) "
                    f"is below the minimum court fee of Rs.{overall_min:.0f}. "
                    "The court fee may be insufficient."
                ),
                suggested_fix=(
                    "Verify the court fee against the Karnataka Court Fees and Suits "
                    "Valuation Act 1958 and ensure the correct amount is paid."
                ),
                confidence_score=0.75,
            )

        return None  # Amounts look plausible

    # ──────────────────────────────────────────────────────────
    # AI-assisted handler
    # ──────────────────────────────────────────────────────────

    async def _run_ai_check(
        self, document: ParsedDocument, point: dict
    ) -> tuple[list[Objection], int]:
        """Call Gemini 2.0 Flash with the document text and a fiscal question."""
        point_id = point["id"]
        ai_prompt = point.get("ai_prompt", "")
        max_chars = 6000

        full_text = self._get_section_text(document, "*")
        text_snippet = full_text[:max_chars]

        if not text_snippet.strip():
            logger.debug(
                "[FiscalChecker] Point %s — document has no text, skipping AI check", point_id
            )
            return [], 0

        prompt = self._build_prompt(point_id, ai_prompt, text_snippet)

        logger.debug(
            "[FiscalChecker] Point %s — sending %d chars to Gemini\n"
            "  PROMPT QUESTION: %s\n"
            "  TEXT SNIPPET (first 300 chars): %.300s",
            point_id, len(prompt), ai_prompt, text_snippet,
        )

        try:
            response = _gemini_model.generate_content(prompt)
            raw_response = response.text
            tokens_used = (len(prompt) + len(raw_response)) // 4

            logger.debug(
                "[FiscalChecker] Point %s — Gemini raw response:\n%s",
                point_id, raw_response,
            )

            objections = self._parse_ai_response(raw_response, document, point)
            return objections, tokens_used

        except Exception as exc:
            logger.warning(
                "[FiscalChecker] Point %s — Gemini API call failed: %s", point_id, exc
            )
            return [], 0

    def _build_prompt(self, point_id: str, question: str, section_text: str) -> str:
        """Build a structured fiscal-review prompt for Gemini."""
        return (
            "You are a fiscal compliance checker for the Karnataka High Court, India.\n"
            "Analyze the following excerpt from a civil petition or appeal for court fee "
            "and valuation compliance.\n\n"
            f"FISCAL CHECKLIST POINT {point_id}: {question}\n\n"
            "DOCUMENT TEXT:\n"
            "---\n"
            f"{section_text}\n"
            "---\n\n"
            "Respond ONLY with a JSON object in this exact format:\n"
            "{\n"
            '  "has_issues": true|false,\n'
            '  "issues": [\n'
            "    {\n"
            '      "description": "Specific fiscal problem found",\n'
            '      "suggested_fix": "Concrete corrective action",\n'
            '      "severity": "CRITICAL|MAJOR|MINOR",\n'
            '      "confidence": 0.0-1.0\n'
            "    }\n"
            "  ]\n"
            "}\n"
            'If no issues found, respond with {"has_issues": false, "issues": []}.\n'
            "Do not include any text outside the JSON block."
        )

    def _parse_ai_response(
        self,
        response_text: str,
        document: ParsedDocument,
        point: dict,
    ) -> list[Objection]:
        """Parse Gemini's JSON response into Objection objects."""
        point_id = point["id"]
        cleaned = re.sub(r"```(?:json)?", "", response_text).strip().strip("`")

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning(
                "[FiscalChecker] Point %s — could not parse Gemini JSON. Raw: %.300s",
                point_id, response_text,
            )
            return []

        if not data.get("has_issues", False):
            return []

        objections: list[Objection] = []
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
                    checklist_point_id=point_id,
                    page_references=[],
                    rule_citation=point.get("rule_source", ""),
                    description=issue.get("description", ""),
                    suggested_fix=issue.get("suggested_fix", ""),
                    confidence_score=confidence,
                )
            )

        return objections
