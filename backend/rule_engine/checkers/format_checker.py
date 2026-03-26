"""
backend/rule_engine/checkers/format_checker.py
──────────────────────────────────────────────────────────────────────────────
Fully deterministic FORMAT checker using PyMuPDF (fitz) geometry APIs.
Zero AI cost — confidence_score is always 1.0 for every objection.

Checks implemented:
  FMT-001  Left margin width (≥ 4 cm / 113.4 pt)
  FMT-002  Body text font size (≥ 12 pt)
  FMT-003  Page size must be A4
  FMT-004  Page numbering on every page
  FMT-005  Right / top / bottom margins
"""

from __future__ import annotations

import re
from typing import Any

import fitz  # PyMuPDF

from backend.rule_engine.checkers.base_checker import BaseChecker
from backend.rule_engine.models import Objection, ParsedDocument


class FormatChecker(BaseChecker):
    """
    Uses fitz page objects (not extracted text) for all geometry checks.
    The document's PDF file path is read from ParsedDocument.pdf_file_path.
    """

    async def check(self, document: ParsedDocument) -> list[Objection]:
        """
        Open the PDF with fitz and run each FORMAT checklist point in turn.

        Args:
            document: Must have pdf_file_path set.

        Returns:
            List of Objection objects for every FORMAT violation found.
        """
        objections: list[Objection] = []

        if not document.pdf_file_path:
            return objections

        try:
            pdf = fitz.open(document.pdf_file_path)
        except Exception as exc:
            return objections  # cannot open — OCR pipeline would have caught real errors

        try:
            for point in self._points:
                if point.get("check_method") != "DETERMINISTIC":
                    continue

                point_id = point["id"]
                params: dict[str, Any] = point.get("parameters", {})

                if point_id == "FMT-001":
                    objections.extend(
                        self._check_left_margin(pdf, document, point, params)
                    )
                elif point_id == "FMT-002":
                    objections.extend(
                        self._check_font_size(pdf, document, point, params)
                    )
                elif point_id == "FMT-003":
                    objections.extend(
                        self._check_page_size(pdf, document, point, params)
                    )
                elif point_id == "FMT-004":
                    objections.extend(
                        self._check_page_numbering(pdf, document, point, params)
                    )
                elif point_id == "FMT-005":
                    objections.extend(
                        self._check_other_margins(pdf, document, point, params)
                    )

        finally:
            pdf.close()

        return objections

    # ──────────────────────────────────────────────────────────
    # FMT-001: Left margin
    # ──────────────────────────────────────────────────────────

    def _check_left_margin(
        self,
        pdf: fitz.Document,
        document: ParsedDocument,
        point: dict,
        params: dict,
    ) -> list[Objection]:
        """
        Measure left margin by finding the minimum x0 coordinate across all
        text blocks on each page. Flag pages where this value is less than
        the required minimum.
        """
        min_left_pt: float = params.get("min_left_margin_pt", 113.4)
        offending_pages: list[int] = []

        for page_num in range(len(pdf)):
            page = pdf[page_num]
            page_number_1indexed = page_num + 1

            blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
            text_x0_values: list[float] = []

            for block in blocks:
                if block.get("type") != 0:  # 0 = text block
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        x0 = span["bbox"][0]
                        text_x0_values.append(x0)

            if not text_x0_values:
                continue

            actual_min_left = min(text_x0_values)
            if actual_min_left < min_left_pt:
                offending_pages.append(page_number_1indexed)

        if not offending_pages:
            return []

        return [
            Objection(
                category="FORMAT",
                severity=point["severity"],
                checklist_point_id=point["id"],
                page_references=offending_pages,
                rule_citation=point["rule_source"],
                description=(
                    f"Left margin is narrower than the required {min_left_pt:.0f} pt "
                    f"(4 cm) on {len(offending_pages)} page(s): {offending_pages}. "
                    "Insufficient margin will cause text to be obscured after binding."
                ),
                suggested_fix=(
                    "Reformat the document to ensure a left margin of at least 4 cm "
                    "(113 pt) on every page before filing."
                ),
                confidence_score=1.0,
            )
        ]

    # ──────────────────────────────────────────────────────────
    # FMT-002: Font size
    # ──────────────────────────────────────────────────────────

    def _check_font_size(
        self,
        pdf: fitz.Document,
        document: ParsedDocument,
        point: dict,
        params: dict,
    ) -> list[Objection]:
        """
        Inspect every text span's size. Collect pages where any span's
        font size is below the minimum (accounting for tolerance).
        Footnotes excluded when exclude_footnotes is true (detected by
        looking at spans below the 85th percentile y-coordinate).
        """
        min_size: float = params.get("min_font_size_pt", 12.0)
        tolerance: float = params.get("tolerance_pt", 0.5)
        exclude_footnotes: bool = params.get("exclude_footnotes", True)
        threshold = min_size - tolerance

        offending_pages: list[int] = []

        for page_num in range(len(pdf)):
            page = pdf[page_num]
            page_height = page.rect.height
            footnote_y_cutoff = page_height * 0.85 if exclude_footnotes else page_height

            blocks = page.get_text("dict")["blocks"]
            for block in blocks:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    line_y = line["bbox"][1]
                    # Skip text in potential footnote zone
                    if line_y > footnote_y_cutoff:
                        continue
                    for span in line.get("spans", []):
                        size = span.get("size", 99)
                        if size < threshold:
                            offending_pages.append(page_num + 1)
                            break  # one violation per page is enough
                    else:
                        continue
                    break

        if not offending_pages:
            return []

        unique_pages = sorted(set(offending_pages))
        return [
            Objection(
                category="FORMAT",
                severity=point["severity"],
                checklist_point_id=point["id"],
                page_references=unique_pages,
                rule_citation=point["rule_source"],
                description=(
                    f"Body text font size is below the required {min_size} pt on "
                    f"{len(unique_pages)} page(s): {unique_pages}."
                ),
                suggested_fix=(
                    f"Ensure all body text is set to at least {min_size} pt. "
                    "Footnotes are excluded from this check."
                ),
                confidence_score=1.0,
            )
        ]

    # ──────────────────────────────────────────────────────────
    # FMT-003: Page size
    # ──────────────────────────────────────────────────────────

    def _check_page_size(
        self,
        pdf: fitz.Document,
        document: ParsedDocument,
        point: dict,
        params: dict,
    ) -> list[Objection]:
        """
        Verify that every page is approximately A4 (595 × 842 pt).
        """
        expected_w: float = params.get("expected_width_pt", 595.28)
        expected_h: float = params.get("expected_height_pt", 841.89)
        tol: float = params.get("tolerance_pt", 5.0)

        offending_pages: list[int] = []

        for page_num in range(len(pdf)):
            page = pdf[page_num]
            rect = page.rect
            # Accept both portrait and landscape A4
            w, h = rect.width, rect.height
            dims = [(w, h), (h, w)]  # landscape swap
            ok = any(
                abs(dw - expected_w) <= tol and abs(dh - expected_h) <= tol
                for dw, dh in dims
            )
            if not ok:
                offending_pages.append(page_num + 1)

        if not offending_pages:
            return []

        return [
            Objection(
                category="FORMAT",
                severity=point["severity"],
                checklist_point_id=point["id"],
                page_references=offending_pages,
                rule_citation=point["rule_source"],
                description=(
                    f"{len(offending_pages)} page(s) are not A4 size: {offending_pages}. "
                    "Karnataka High Court accepts only A4 (210 × 297 mm) paper."
                ),
                suggested_fix=(
                    "Print or re-export the document on A4 paper. "
                    "Check printer/PDF export settings."
                ),
                confidence_score=1.0,
            )
        ]

    # ──────────────────────────────────────────────────────────
    # FMT-004: Page numbering
    # ──────────────────────────────────────────────────────────

    def _check_page_numbering(
        self,
        pdf: fitz.Document,
        document: ParsedDocument,
        point: dict,
        params: dict,
    ) -> list[Objection]:
        """
        Detect whether each page carries a visible page number.

        Strategy: search header (top strip) and footer (bottom strip) zones
        for text that consists only of digits (or digits surrounded by
        whitespace / punctuation such as "- 5 -" or "[5]").
        """
        top_strip: float = params.get("look_in_top_strip_pt", 72)
        bottom_strip: float = params.get("look_in_bottom_strip_pt", 72)
        number_re = re.compile(r"^\s*[\[\-]?\s*\d+\s*[\]\-]?\s*$")

        missing_pages: list[int] = []

        for page_num in range(len(pdf)):
            page = pdf[page_num]
            h = page.rect.height

            header_rect = fitz.Rect(0, 0, page.rect.width, top_strip)
            footer_rect = fitz.Rect(0, h - bottom_strip, page.rect.width, h)

            header_text = page.get_text("text", clip=header_rect).strip()
            footer_text = page.get_text("text", clip=footer_rect).strip()

            found = False
            for zone_text in (header_text, footer_text):
                for line in zone_text.splitlines():
                    if number_re.match(line.strip()):
                        found = True
                        break
                if found:
                    break

            if not found:
                missing_pages.append(page_num + 1)

        if not missing_pages:
            return []

        return [
            Objection(
                category="FORMAT",
                severity=point["severity"],
                checklist_point_id=point["id"],
                page_references=missing_pages,
                rule_citation=point["rule_source"],
                description=(
                    f"{len(missing_pages)} page(s) appear to be missing page numbers: "
                    f"{missing_pages}."
                ),
                suggested_fix=(
                    "Add sequential page numbers to all pages. "
                    "Numbers should appear at the bottom-centre or top-right of each page."
                ),
                confidence_score=1.0,
            )
        ]

    # ──────────────────────────────────────────────────────────
    # FMT-005: Right / top / bottom margins
    # ──────────────────────────────────────────────────────────

    def _check_other_margins(
        self,
        pdf: fitz.Document,
        document: ParsedDocument,
        point: dict,
        params: dict,
    ) -> list[Objection]:
        """
        Check right, top, and bottom margins by measuring text block extents
        vs. page dimensions.
        """
        min_right: float = params.get("min_right_margin_pt", 70.9)
        min_top: float = params.get("min_top_margin_pt", 70.9)
        min_bottom: float = params.get("min_bottom_margin_pt", 70.9)

        offending: dict[str, list[int]] = {
            "right": [], "top": [], "bottom": []
        }

        for page_num in range(len(pdf)):
            page = pdf[page_num]
            pw = page.rect.width
            ph = page.rect.height

            blocks = page.get_text("dict")["blocks"]
            x1_values, y0_values, y1_values = [], [], []

            for block in blocks:
                if block.get("type") != 0:
                    continue
                bbox = block["bbox"]
                x1_values.append(bbox[2])
                y0_values.append(bbox[1])
                y1_values.append(bbox[3])

            if not x1_values:
                continue

            pn = page_num + 1
            max_x1 = max(x1_values)
            min_y0 = min(y0_values)
            max_y1 = max(y1_values)

            actual_right = pw - max_x1
            actual_top = min_y0
            actual_bottom = ph - max_y1

            if actual_right < min_right:
                offending["right"].append(pn)
            if actual_top < min_top:
                offending["top"].append(pn)
            if actual_bottom < min_bottom:
                offending["bottom"].append(pn)

        results: list[Objection] = []

        for margin_name, pages in offending.items():
            if not pages:
                continue
            min_val = {"right": min_right, "top": min_top, "bottom": min_bottom}[margin_name]
            results.append(
                Objection(
                    category="FORMAT",
                    severity=point["severity"],
                    checklist_point_id=point["id"],
                    page_references=sorted(pages),
                    rule_citation=point["rule_source"],
                    description=(
                        f"The {margin_name} margin is narrower than the required "
                        f"{min_val:.0f} pt (2.5 cm) on {len(pages)} page(s): {sorted(pages)}."
                    ),
                    suggested_fix=(
                        f"Increase the {margin_name} margin to at least 2.5 cm "
                        "and re-export the document."
                    ),
                    confidence_score=1.0,
                )
            )

        return results
