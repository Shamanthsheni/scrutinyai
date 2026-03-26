"""
backend/ocr/section_detector.py
──────────────────────────────────────────────────────────────────────────────
SectionDetector: scans raw_text_by_page to detect the six canonical sections
of a Karnataka High Court civil filing and assigns page ranges.

Detected sections:
  INDEX             → table of contents page
  SYNOPSIS          → brief facts / list of dates
  MEMO_OF_PETITION  → main petition/appeal body
  VERIFYING_AFFIDAVIT → affidavit at end of petition
  ANNEXURES         → exhibits (Annexure A, B, C…)
  VAKALATHNAMA      → advocate authorisation form

Detection strategy:
  • Scan the first HEADER_SCAN_CHARS (200) characters of each page.
  • Match against compiled regex patterns (English + Kannada).
  • When a new section header is found, close the previous section and
    open a new one.
  • Same-page conflict → SECTION_PRIORITY resolves which section wins.
  • Missing sections are silently omitted from the output dict.
  • One page belongs to exactly one section (no intra-page splitting).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from backend.rule_engine.models import ParsedDocument

logger = logging.getLogger(__name__)

# ── Keyword patterns ───────────────────────────────────────────
# All patterns are compiled with IGNORECASE | UNICODE.
# Kannada Unicode ranges are included as-is (re handles them correctly).

SECTION_PATTERNS: dict[str, list[str]] = {
    "INDEX": [
        r"\bINDEX\b",
        r"\bTABLE\s+OF\s+CONTENTS\b",
        r"\bSl\.?\s*No\.?\s+Particulars\b",        # common HC index header
        r"\bLIST\s+OF\s+DOCUMENTS\b",
        r"ಅನುಕ್ರಮಣಿಕೆ",                             # Kannada: anukramaṇike
    ],
    "SYNOPSIS": [
        r"\bSYNOPSIS\s+AND\s+LIST\s+OF\s+DATES\b",
        r"\bSYNOPSIS\s+&\s+LIST\s+OF\s+DATES\b",
        r"\bSYNOPSIS\b",
        r"\bLIST\s+OF\s+DATES\b",
        r"\bBRIEF\s+FACTS\b",
        r"\bSTATEMENT\s+OF\s+FACTS\b",
        r"ಸಂಕ್ಷಿಪ್ತ\s*ವಿವರ",                       # saṅkṣipta vivara
        r"ದಿನಾಂಕಗಳ\s*ಪಟ್ಟಿ",                        # dinānkagaḷa paṭṭi
    ],
    "MEMO_OF_PETITION": [
        r"\bMEMORANDUM\s+OF\s+(?:PETITION|APPEAL|WRIT\s+PETITION)\b",
        r"\bMEMO\s+OF\s+(?:PETITION|APPEAL)\b",
        r"\bWRIT\s+PETITION\b",
        r"\bCIVIL\s+(?:REVISION\s+)?PETITION\b",
        r"\bPETITION\s+UNDER\b",
        r"\bAPPEAL\s+UNDER\b",
        r"\bREGULAR\s+FIRST\s+APPEAL\b",
        r"\bMISCELLANEOUS\s+PETITION\b",
        r"ಮನವಿ\s*ಜ್ಞಾಪನ",                          # manavi jñāpana
        r"ರಿಟ್\s*ಮನವಿ",                              # riṭ manavi (writ petition)
    ],
    "VERIFYING_AFFIDAVIT": [
        r"\bVERIF(?:YING|ICATION)\s+AFFIDAVIT\b",
        r"\bAFFIDAVIT\s+OF\s+VERIFICATION\b",
        r"\bAFFIDAVIT\b",
        r"\bVERIFICATION\b",
        r"\bSWORN\s+(?:BEFORE|AT)\b",
        r"ಪರಿಶೀಲನಾ\s*ಪ್ರಮಾಣ",                      # pariśīlanā pramāṇa
        r"ಪ್ರಮಾಣ\s*ಪತ್ರ",                           # pramāṇa patra
    ],
    "ANNEXURES": [
        r"\bANNEXURE\s*[-–—]?\s*[A-Z0-9]",
        r"\bANNEXURE\s*[-–—]?\s*\d",
        r"\bEXHIBIT\s*[-–—]?\s*[A-Z0-9]",
        r"\bDOCUMENT\s+LIST\b",
        r"\bLIST\s+OF\s+ANNEXURES\b",
        r"ಅನುಬಂಧ",                                   # anubandha
        r"ದಾಖಲೆಗಳ\s*ಪಟ್ಟಿ",                          # dākhalegaḷa paṭṭi
    ],
    "VAKALATHNAMA": [
        r"\bVAKALATH?NAMA\b",
        r"\bVAKALATNAMAH?\b",
        r"\bMEMO\s+OF\s+APPEARANCE\b",
        r"\bPOWER\s+OF\s+ATTORNEY\b",
        r"\bADVOCATE['']?S?\s+AUTHORITY\b",
        r"ವಕಾಲತ್",                                   # vakālatnāme
        r"ಅಧಿಕಾರ\s*ಪತ್ರ",                           # adhikāra patra
    ],
}

# Higher index = higher priority (used when two section headers appear on same page)
# VAKALATHNAMA has highest priority (index 5), INDEX has lowest (index 0)
SECTION_PRIORITY: list[str] = [
    "INDEX",
    "SYNOPSIS",
    "MEMO_OF_PETITION",
    "ANNEXURES",
    "VERIFYING_AFFIDAVIT",
    "VAKALATHNAMA",
]


class SectionDetector:
    """
    Identifies section page ranges within a ParsedDocument by scanning
    the top of each page for known section header patterns.

    Usage:
        detector = SectionDetector()
        document = detector.detect(document)
    """

    HEADER_SCAN_CHARS: int = 200  # chars from top of page to examine

    def __init__(
        self,
        patterns: dict[str, list[str]] | None = None,
    ) -> None:
        """
        Compile regex patterns for each section.

        Args:
            patterns: Override SECTION_PATTERNS for testing.
                      If None, uses the module-level SECTION_PATTERNS.
        """
        raw_patterns = patterns if patterns is not None else SECTION_PATTERNS
        self._compiled: dict[str, list[re.Pattern]] = {
            section: [
                re.compile(pat, re.IGNORECASE | re.UNICODE)
                for pat in pat_list
            ]
            for section, pat_list in raw_patterns.items()
        }

    def detect(self, document: ParsedDocument) -> ParsedDocument:
        """
        Scan all pages in order and assign each to a section.

        Mutates document.sections and document.raw_text_by_section in place.
        Returns the same ParsedDocument instance (for chaining).

        Args:
            document: Must have raw_text_by_page populated (from PDFParser).

        Returns:
            The same ParsedDocument with sections and raw_text_by_section populated.
        """
        if not document.raw_text_by_page:
            logger.warning(
                "SectionDetector called on document with empty raw_text_by_page "
                "(file_id=%s). No sections will be detected.",
                document.file_id,
            )
            return document

        # active_info: (section_name, start_page) or None
        active_info: tuple[str, int] | None = None
        detected_sections: dict[str, tuple[int, int]] = {}

        sorted_pages = sorted(document.raw_text_by_page.keys())

        for page_num in sorted_pages:
            full_text = document.raw_text_by_page.get(page_num, "")
            header = full_text[: self.HEADER_SCAN_CHARS]
            matched_section = self._match_page(header)

            current_section = active_info[0] if active_info else None

            if matched_section is None or matched_section == current_section:
                # No section change on this page
                continue

            # A new section header was found on this page
            if active_info is not None:
                prev_name, prev_start = active_info
                self._close_section(
                    detected_sections, prev_name, prev_start, page_num - 1
                )
                logger.debug(
                    "file_id=%s: section '%s' closed at page %d",
                    document.file_id,
                    prev_name,
                    page_num - 1,
                )

            logger.debug(
                "file_id=%s: section '%s' opens at page %d",
                document.file_id,
                matched_section,
                page_num,
            )
            active_info = (matched_section, page_num)

        # Close the last open section at the document's final page
        if active_info is not None:
            last_name, last_start = active_info
            self._close_section(
                detected_sections, last_name, last_start, max(sorted_pages)
            )

        # Build raw_text_by_section from detected page ranges
        raw_text_by_section: dict[str, str] = {
            section: self._concatenate_pages(
                document.raw_text_by_page, start, end
            )
            for section, (start, end) in detected_sections.items()
        }

        # Mutate the document in place
        document.sections = detected_sections
        document.raw_text_by_section = raw_text_by_section

        logger.info(
            "file_id=%s: sections detected: %s",
            document.file_id,
            {s: f"pp.{v[0]}-{v[1]}" for s, v in detected_sections.items()},
        )

        return document

    # ── Pattern matching ───────────────────────────────────────

    def _match_page(self, page_header: str) -> str | None:
        """
        Test a page's header text against all compiled section patterns.

        If multiple patterns from different sections match, resolve the
        conflict by returning the section with the highest SECTION_PRIORITY
        index.

        Args:
            page_header: First HEADER_SCAN_CHARS characters of the page text.

        Returns:
            Section name (str) if any pattern matches, else None.
        """
        matched: list[str] = []

        for section, patterns in self._compiled.items():
            for pat in patterns:
                if pat.search(page_header):
                    matched.append(section)
                    break  # one match per section is enough

        if not matched:
            return None

        if len(matched) == 1:
            return matched[0]

        # Priority tie-break: highest SECTION_PRIORITY index wins
        def priority(s: str) -> int:
            try:
                return SECTION_PRIORITY.index(s)
            except ValueError:
                return -1

        return max(matched, key=priority)

    # ── Section management ─────────────────────────────────────

    def _close_section(
        self,
        sections: dict[str, tuple[int, int]],
        section_name: str,
        start_page: int,
        end_page: int,
    ) -> None:
        """
        Record the (start_page, end_page) tuple for the completed section.

        If the same section header appears twice in the document (rare but
        possible), we keep the first occurrence's start page and update
        only the end page to the latest one seen.
        """
        if section_name in sections:
            existing_start = sections[section_name][0]
            sections[section_name] = (existing_start, end_page)
        else:
            sections[section_name] = (start_page, end_page)

    def _concatenate_pages(
        self,
        raw_text_by_page: dict[int, str],
        start_page: int,
        end_page: int,
    ) -> str:
        """
        Join text from start_page to end_page (inclusive) with
        page-break marker lines: "\\n--- PAGE {n} ---\\n".

        Args:
            raw_text_by_page: 1-indexed dict of page texts.
            start_page:       Inclusive start (1-indexed).
            end_page:         Inclusive end (1-indexed).

        Returns:
            Concatenated string of all page texts in the range.
        """
        parts: list[str] = []
        for pn in range(start_page, end_page + 1):
            text = raw_text_by_page.get(pn, "")
            parts.append(f"\n--- PAGE {pn} ---\n{text}")
        return "".join(parts).strip()
