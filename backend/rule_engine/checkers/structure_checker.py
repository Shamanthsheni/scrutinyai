"""
backend/rule_engine/checkers/structure_checker.py
──────────────────────────────────────────────────────────────────────────────
Hybrid STRUCTURE checker.

Deterministic checks (confidence = 1.0):
  STR-001  Index / ToC present
  STR-006  Verifying affidavit present
  STR-007  Signature on every page

AI-assisted checks (Gemini 2.0 Flash, confidence from model response):
  STR-002  Synopsis and list of dates quality
  STR-003  Prayer clause completeness
  STR-004  Grounds coherence
  STR-005  Vakalatnama compliance

AI calls are limited to 2-5 pages per check for cost control.
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


class StructureChecker(BaseChecker):
    """
    Runs both deterministic and AI-assisted structure checks.
    """

    async def check(self, document: ParsedDocument) -> list[Objection]:
        """
        Route each checklist point to the correct handler based on check_method.
        AI checks are run sequentially to respect API rate limits.
        """
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
        """Dispatch to the correct deterministic helper."""
        point_id = point["id"]

        if point_id == "STR-001":
            return self._check_section_present(
                document, point, "INDEX",
                "INDEX (Table of Contents)"
            )
        elif point_id == "STR-006":
            return self._check_section_present(
                document, point, "VERIFYING_AFFIDAVIT",
                "VERIFYING AFFIDAVIT"
            )
        elif point_id == "STR-007":
            return self._check_signature_presence(document, point)

        return None

    def _check_section_present(
        self,
        document: ParsedDocument,
        point: dict,
        section_name: str,
        display_name: str,
    ) -> Objection | None:
        """
        Return an Objection if the required section is absent from the document.
        """
        if section_name in document.sections:
            return None

        return Objection(
            category="STRUCTURE",
            severity=point["severity"],
            checklist_point_id=point["id"],
            page_references=[],
            rule_citation=point["rule_source"],
            description=(
                f"The {display_name} section could not be located in the filing. "
                "This section is mandatory for all civil filings in the Karnataka High Court."
            ),
            suggested_fix=(
                f"Ensure the {display_name} is included as a clearly labelled section "
                "in the filing and uses the standard header so it can be detected."
            ),
            confidence_score=1.0,
        )

    def _check_signature_presence(
        self, document: ParsedDocument, point: dict
    ) -> Objection | None:
        """
        For scanned PDFs: always emit a manual-verification objection
        (confidence = 0.75 per design spec, since ink signature detection
        on rasterised images is unreliable).

        For text-native PDFs: look for /Sig annotation dictionaries or
        image blocks with area ≥ min_signature_area_px as a proxy.
        This check is inherently heuristic — confidence stays at 0.75
        to route the objection to the "verify manually" bucket.
        """
        params = point.get("parameters", {})
        scanned_confidence: float = params.get("scanned_doc_default_confidence", 0.75)

        is_scanned = document.ocr_path_used == "TESSERACT"

        # For scanned docs: always flag for manual verification
        if is_scanned:
            return Objection(
                category="STRUCTURE",
                severity=point["severity"],
                checklist_point_id=point["id"],
                page_references=list(range(1, document.total_pages + 1)),
                rule_citation=point["rule_source"],
                description=(
                    "This document was identified as a scanned PDF. "
                    "Automatic ink-signature detection on scanned pages is unreliable. "
                    "Manual verification is required to confirm that every page bears the "
                    "advocate's or party-in-person's signature."
                ),
                suggested_fix=(
                    "Physically verify that all pages are signed. "
                    "Consider re-filing as a text-native PDF with digital signatures."
                ),
                confidence_score=scanned_confidence,
            )

        # For text-native docs: look for annotation hints
        # We use fitz if available; otherwise flag for manual review at 0.75
        try:
            import fitz

            if not document.pdf_file_path:
                raise FileNotFoundError("no pdf_file_path")

            pdf = fitz.open(document.pdf_file_path)
            try:
                unsigned_pages: list[int] = []
                for page_num in range(len(pdf)):
                    page = pdf[page_num]
                    has_sig_annot = any(
                        annot.type[0] == 1  # Fitz type 1 = Widget / Sig
                        for annot in page.annots()
                    )
                    has_image_block = any(
                        block.get("type") == 1  # image block
                        and (block["bbox"][2] - block["bbox"][0])
                        * (block["bbox"][3] - block["bbox"][1])
                        >= params.get("min_signature_area_px", 2000)
                        for block in page.get_text("dict")["blocks"]
                    )
                    if not has_sig_annot and not has_image_block:
                        unsigned_pages.append(page_num + 1)
            finally:
                pdf.close()

            if not unsigned_pages:
                return None

            return Objection(
                category="STRUCTURE",
                severity=point["severity"],
                checklist_point_id=point["id"],
                page_references=unsigned_pages,
                rule_citation=point["rule_source"],
                description=(
                    f"{len(unsigned_pages)} page(s) appear to lack a visible signature: "
                    f"{unsigned_pages}. Note: automatic signature detection may miss "
                    "hand-drawn or unconventional signatures."
                ),
                suggested_fix=(
                    "Ensure the advocate or party-in-person has signed every page "
                    "before filing."
                ),
                confidence_score=scanned_confidence,  # 0.75 — always manual review
            )

        except Exception:
            # If fitz detection fails for any reason, flag for manual review
            return Objection(
                category="STRUCTURE",
                severity=point["severity"],
                checklist_point_id=point["id"],
                page_references=[],
                rule_citation=point["rule_source"],
                description=(
                    "Could not automatically verify signatures on all pages. "
                    "Manual verification is required."
                ),
                suggested_fix="Verify that every page has been signed by the advocate.",
                confidence_score=scanned_confidence,
            )

    # ──────────────────────────────────────────────────────────
    # AI-assisted handler
    # ──────────────────────────────────────────────────────────

    async def _run_ai_check(
        self, document: ParsedDocument, point: dict
    ) -> tuple[list[Objection], int]:
        """
        Call Gemini 2.0 Flash with scoped section text only.

        Returns (objections, tokens_used).
        """
        section_scope: str = point.get("section_scope", "*")
        max_pages: int = point.get("parameters", {}).get("max_pages_to_send", 4)

        section_text = self._get_section_text(document, section_scope)
        if not section_text.strip():
            # Section not found — emit a deterministic missing-section objection
            return (
                [
                    Objection(
                        category="STRUCTURE",
                        severity=point["severity"],
                        checklist_point_id=point["id"],
                        page_references=[],
                        rule_citation=point["rule_source"],
                        description=(
                            f"Section '{section_scope}' could not be located in the filing; "
                            f"cannot perform AI check '{point['title']}'."
                        ),
                        suggested_fix=(
                            f"Ensure the '{section_scope}' section is present and "
                            "clearly labelled in the document."
                        ),
                        confidence_score=1.0,
                    )
                ],
                0,
            )

        # Truncate to max_pages worth of text (rough: 2 000 chars per page)
        chars_limit = max_pages * 2000
        section_text_trimmed = section_text[:chars_limit]

        prompt = self._build_prompt(point, section_text_trimmed)

        try:
            response = _gemini_model.generate_content(prompt)
            tokens_used = self._estimate_tokens(prompt, response.text)
            return self._parse_ai_response(response.text, document, point), tokens_used
        except Exception as exc:
            logger.warning(
                "Gemini API call failed for point %s: %s", point["id"], exc
            )
            return [], 0

    def _build_prompt(self, point: dict, section_text: str) -> str:
        """Render the ai_prompt_template by substituting {{section_text}}."""
        template: str = point.get("ai_prompt_template", "")
        return template.replace("{{section_text}}", section_text)

    def _parse_ai_response(
        self,
        response_text: str,
        document: ParsedDocument,
        point: dict,
    ) -> list[Objection]:
        """
        Parse Gemini's JSON response into a list of Objection objects.
        """
        # Strip markdown code fences if present
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
        section_pages = self._get_section_pages(document, point.get("section_scope", "*"))

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
                    checklist_point_id=point["id"],
                    page_references=section_pages,
                    rule_citation=point["rule_source"],
                    description=issue.get("description", ""),
                    suggested_fix=issue.get("suggested_fix", ""),
                    confidence_score=confidence,
                )
            )

        return objections

    @staticmethod
    def _estimate_tokens(prompt: str, response: str) -> int:
        """
        Rough approximation: 1 token ≈ 4 characters.
        Gemini SDK does not always expose exact usage counts in basic calls.
        """
        return (len(prompt) + len(response)) // 4
