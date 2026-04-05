"""
backend/rule_engine/checkers/structure_checker.py
──────────────────────────────────────────────────────────────────────────────
Hybrid STRUCTURE checker — works with the new civil_checklist.json schema.

Schema fields used:
  id, check_method, check_type, ai_prompt, section_title,
  category, severity, rule_source, description

Deterministic check_type values handled:
  "presence"  → look for keyword evidence in full document text
  "format"    → look for specific formatting evidence

AI_ASSISTED checks:
  Uses the `ai_prompt` field as the Gemini system prompt.
  Sends the relevant section text (or full doc if section not found).
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import google.generativeai as genai

from backend.rule_engine.checkers.base_checker import BaseChecker
from backend.rule_engine.models import Objection, ParsedDocument

logger = logging.getLogger(__name__)

# Configure Gemini once at import time
genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))
_gemini_model = genai.GenerativeModel("gemini-2.0-flash")

# Keyword sets used for deterministic "presence" checks keyed by point id
# These are heuristics — the AI checks handle the nuanced cases.
_PRESENCE_KEYWORDS: dict[str, list[str]] = {
    "I-a":    ["signed", "dated", "counsel", "advocate"],
    "I-b":    ["vakalath", "vakalatnama", "affidavit", "signed"],
    "I-c":    ["index", "sl.no", "s.no", "page no", "paginated"],
    "II-c":   ["173(1)", "motor vehicles act", "statutory deposit", "mvc"],
    "II-d":   ["30(1)", "workmen", "award", "deposit", "receipt"],
    "III-b":  ["condonation", "delay", "ia no", "i.a.", "days of delay"],
    "III-c":  ["cross-objection", "notice", "service", "date of service"],
    "IV-a":   ["synopsis", "list of dates", "brief facts"],
    "V-d":    ["address for service", "local address", "advocate for appellant"],
    "V-e":    ["impugned", "judgment dated", "order dated", "decree dated"],
    "V-h":    ["limitation", "within time", "period of limitation"],
    "V-i":    ["prayer", "wherefore", "it is humbly prayed"],
    "VI-b":   ["court fee", "c.f.", "receipt", "treasury"],
    "VI-e":   ["land acquisition", "sec.48", "section 48", "section 23"],
    "VII-a":  ["certified copy", "c.c.", "decree", "valuation slip", "impugned order"],
    "VII-b":  ["typed copy", "manuscript", "legible"],
    "VII-c":  ["true copy", "attested", "as per original"],
    "VIII-a": ["vakalath", "vakalatnama", "signed", "dated"],
    "VIII-b": ["identified by", "executant", "signature identified"],
    "VIII-c": ["enrollment", "enrolment", "bar council", "counsel"],
    "VIII-d": ["appellant", "petitioner", "executant"],
    "VIII-e": ["gpa", "general power of attorney", "guardian", "natural guardian"],
    "VIII-f": ["gpa", "power of attorney", "filed"],
    "VIII-g": ["seal", "stamp", "company", "firm", "trust"],
    "VIII-h": ["welfare stamp", "rs.50", "rs. 50", "₹50", "advocate welfare"],
    "IX-a":   ["ia", "i.a.", "interlocutory", "affidavit"],
    "IX-b":   ["schedule", "property", "injunction", "temporary injunction"],
    "IX-c":   ["order 41 rule 27", "o.41 r.27", "additional documents", "documents filed"],
    "IX-d":   ["attested", "certified", "competent authority"],
    "IX-e":   ["welfare stamp", "rs.20", "rs. 20", "₹20"],
    "IX-f":   ["sworn", "oath", "notary", "serial no", "attestation"],
    "IX-g":   ["stitched", "separately", "ia separately"],
    "X-a":    ["revision", "pending", "proceedings", "details of"],
    "X-b":    ["caveator", "respondent", "acknowledgment", "served", "notice"],
    "X-c":    ["genealogical", "family tree", "partition"],
    "X-d":    ["second set", "fc", "mc", "gwc"],
    "X-e":    ["death certificate", "legal representatives", "lr", "lrs", "lrof"],
}


class StructureChecker(BaseChecker):
    """
    Runs both deterministic presence/format checks and AI-assisted checks
    against the new civil_checklist.json schema.
    """

    async def check(self, document: ParsedDocument) -> list[Objection]:
        """
        Route each STRUCTURE checklist point to the correct handler.
        """
        objections: list[Objection] = []
        self._ai_tokens_used = 0

        logger.debug(
            "[StructureChecker] Starting — %d points to check", len(self._points)
        )

        for point in self._points:
            method = point.get("check_method", "DETERMINISTIC")
            point_id = point["id"]
            logger.debug(
                "[StructureChecker] Point %s | method=%s | check_type=%s",
                point_id, method, point.get("check_type"),
            )

            if method == "DETERMINISTIC":
                result = self._run_deterministic(document, point)
                if result:
                    logger.debug(
                        "[StructureChecker] Point %s → OBJECTION raised", point_id
                    )
                    objections.append(result)
                else:
                    logger.debug("[StructureChecker] Point %s → PASS", point_id)

            elif method == "AI_ASSISTED":
                new_objections, tokens = await self._run_ai_check(document, point)
                logger.debug(
                    "[StructureChecker] Point %s → AI returned %d objection(s), %d tokens",
                    point_id, len(new_objections), tokens,
                )
                objections.extend(new_objections)
                self._ai_tokens_used += tokens

        logger.debug(
            "[StructureChecker] Done — %d total objection(s), %d AI tokens",
            len(objections), self._ai_tokens_used,
        )
        return objections

    # ──────────────────────────────────────────────────────────
    # Deterministic handler
    # ──────────────────────────────────────────────────────────

    def _run_deterministic(
        self, document: ParsedDocument, point: dict
    ) -> Objection | None:
        """Dispatch to presence or format check."""
        check_type = point.get("check_type", "presence")

        if check_type in ("presence", "format"):
            return self._check_keyword_presence(document, point)
        return None

    def _check_keyword_presence(
        self, document: ParsedDocument, point: dict
    ) -> Objection | None:
        """
        Search the entire document text for any of the heuristic keywords
        associated with this checklist point.

        Returns an Objection if NO keyword is found.
        Returns None (pass) if at least one keyword is found or if no
        keywords are configured for this point (to avoid false positives).
        """
        point_id = point["id"]
        keywords = _PRESENCE_KEYWORDS.get(point_id, [])

        if not keywords:
            logger.debug(
                "[StructureChecker] Point %s — no keywords configured, skipping presence check",
                point_id,
            )
            return None

        full_text = self._get_section_text(document, "*").lower()
        logger.debug(
            "[StructureChecker] Point %s — searching %d chars for keywords %s",
            point_id, len(full_text), keywords,
        )

        for kw in keywords:
            if kw.lower() in full_text:
                logger.debug(
                    "[StructureChecker] Point %s — keyword '%s' found → PASS", point_id, kw
                )
                return None

        logger.debug(
            "[StructureChecker] Point %s — no keywords found → OBJECTION", point_id
        )
        return Objection(
            category="STRUCTURE",
            severity=point["severity"],
            checklist_point_id=point_id,
            page_references=[],
            rule_citation=point.get("rule_source", ""),
            description=(
                f"{point.get('description', 'Required element missing.')} "
                "This item could not be located in the document."
            ),
            suggested_fix=(
                f"Ensure the required element is present and clearly labelled. "
                f"See: {point.get('rule_source', 'Karnataka HC Rules')}."
            ),
            confidence_score=0.85,
        )

    # ──────────────────────────────────────────────────────────
    # AI-assisted handler
    # ──────────────────────────────────────────────────────────

    async def _run_ai_check(
        self, document: ParsedDocument, point: dict
    ) -> tuple[list[Objection], int]:
        """
        Call Gemini 2.0 Flash with the document text and structured prompt.

        Returns (objections, tokens_used).
        """
        point_id = point["id"]
        ai_prompt = point.get("ai_prompt", "")
        max_chars = 8000  # ~4 pages of text

        full_text = self._get_section_text(document, "*")
        text_snippet = full_text[:max_chars]

        if not text_snippet.strip():
            logger.debug(
                "[StructureChecker] Point %s — document has no text, skipping AI check",
                point_id,
            )
            return [], 0

        prompt = self._build_prompt(point_id, ai_prompt, text_snippet)

        logger.debug(
            "[StructureChecker] Point %s — sending %d chars to Gemini\n"
            "  PROMPT QUESTION: %s\n"
            "  TEXT SNIPPET (first 300 chars): %.300s",
            point_id, len(prompt), ai_prompt, text_snippet,
        )

        try:
            response = _gemini_model.generate_content(prompt)
            raw_response = response.text
            tokens_used = self._estimate_tokens(prompt, raw_response)

            logger.debug(
                "[StructureChecker] Point %s — Gemini raw response:\n%s",
                point_id, raw_response,
            )

            objections = self._parse_ai_response(raw_response, document, point)
            return objections, tokens_used

        except Exception as exc:
            logger.warning(
                "[StructureChecker] Point %s — Gemini API call failed: %s",
                point_id, exc,
            )
            return [], 0

    def _build_prompt(self, point_id: str, question: str, section_text: str) -> str:
        """Build a structured JSON-requesting prompt for Gemini."""
        return (
            "You are a legal document checker for the Karnataka High Court, India.\n"
            "Analyze the following excerpt from a civil petition or appeal.\n\n"
            f"CHECKLIST POINT {point_id}: {question}\n\n"
            "DOCUMENT TEXT:\n"
            "---\n"
            f"{section_text}\n"
            "---\n\n"
            "Respond ONLY with a JSON object in this exact format:\n"
            "{\n"
            '  "has_issues": true|false,\n'
            '  "issues": [\n'
            "    {\n"
            '      "description": "Specific problem found",\n'
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
        """
        Parse Gemini's JSON response into Objection objects.
        """
        point_id = point["id"]
        cleaned = re.sub(r"```(?:json)?", "", response_text).strip().strip("`")

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning(
                "[StructureChecker] Point %s — could not parse Gemini JSON. Raw: %.300s",
                point_id, response_text,
            )
            return []

        if not data.get("has_issues", False):
            return []

        objections: list[Objection] = []
        all_pages = sorted(document.raw_text_by_page.keys())

        for issue in data.get("issues", []):
            raw_confidence = float(issue.get("confidence", 0.80))
            confidence = max(0.0, min(1.0, raw_confidence))
            raw_severity = issue.get("severity", point["severity"])
            if raw_severity not in ("CRITICAL", "MAJOR", "MINOR"):
                raw_severity = point["severity"]

            objections.append(
                Objection(
                    category="STRUCTURE",
                    severity=raw_severity,
                    checklist_point_id=point_id,
                    page_references=all_pages[:3],  # reference first few pages
                    rule_citation=point.get("rule_source", ""),
                    description=issue.get("description", ""),
                    suggested_fix=issue.get("suggested_fix", ""),
                    confidence_score=confidence,
                )
            )

        return objections

    @staticmethod
    def _estimate_tokens(prompt: str, response: str) -> int:
        return (len(prompt) + len(response)) // 4
