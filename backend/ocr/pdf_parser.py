"""
backend/ocr/pdf_parser.py
──────────────────────────────────────────────────────────────────────────────
PDFParser: reads a PDF file from disk and produces a ParsedDocument with:
  - SHA-256 file hash
  - text extracted via PyMuPDF (text-native) or Tesseract (scanned)
  - ocr_path_used set correctly
  - raw_text_by_page populated (1-indexed)
  - overall_ocr_confidence

Routing logic:
  1. Compute SHA-256 hash of file bytes.
  2. Sample first 10 pages with PyMuPDF.
     If avg chars/page > 50 → PYMUPDF path.
     Else → TESSERACT path.
  3. PYMUPDF: extract text page-by-page, confidence = 1.0.
  4. TESSERACT: rasterise at 150 DPI, OCR with ProcessPoolExecutor,
     average page confidences.
     If overall < 0.85 → log warning, continue (no DocAI fallback).
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

from backend.rule_engine.models import ParsedDocument

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────

TEXT_NATIVE_THRESHOLD: int = 50      # avg chars/page to count as text-native
TESSERACT_INITIAL_DPI: int = 150     # first-pass DPI (fast)
TESSERACT_RETRY_DPI: int = 300       # retry DPI (used if confidence still low after first pass)
LOW_CONFIDENCE_THRESHOLD: float = 0.85
SAMPLE_PAGES: int = 10              # number of pages sampled for text-native detection


# ── Tesseract worker function (module-level for pickling) ──────

def _ocr_single_page_worker(
    pdf_path: str, page_num: int, dpi: int
) -> tuple[int, str, float]:
    """
    Worker function executed in a subprocess via ProcessPoolExecutor.

    Opens the PDF independently (each worker process has its own copy),
    rasterises the requested page, runs Tesseract, and returns
    (page_1indexed, text, confidence_0_to_1).

    This function is at module level to be picklable by multiprocessing.
    """
    import pytesseract
    from PIL import Image
    import fitz as _fitz

    doc = _fitz.open(pdf_path)
    try:
        page = doc[page_num]
        mat = _fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat, colorspace=_fitz.csRGB)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    finally:
        doc.close()

    # Run Tesseract with output_type=dict for per-word confidences
    data = pytesseract.image_to_data(
        img,
        lang="eng",
        output_type=pytesseract.Output.DICT,
        config="--psm 3",
    )

    text = pytesseract.image_to_string(img, lang="eng", config="--psm 3")

    # Compute average confidence, ignoring -1 values (non-text regions)
    confidences = [
        c for c in data["conf"] if isinstance(c, (int, float)) and c >= 0
    ]
    avg_conf = (sum(confidences) / len(confidences) / 100.0) if confidences else 0.0

    return page_num + 1, text, avg_conf


# ── PDFParser class ────────────────────────────────────────────

class PDFParser:
    """
    Reads a PDF from disk and produces a ParsedDocument with OCR text.

    Section detection is NOT performed here — call SectionDetector.detect()
    on the returned ParsedDocument to populate sections and raw_text_by_section.
    """

    def __init__(self, file_path: str | Path) -> None:
        """
        Store the file path. File is not opened until parse() is called.

        Args:
            file_path: Absolute path to the PDF file on disk.
        """
        self._file_path = Path(file_path)

    async def parse(self, file_id: str = "") -> ParsedDocument:
        """
        Full parsing pipeline:
          hash → detect text-native vs scanned → extract text → build ParsedDocument.

        Args:
            file_id: Supabase storage file ID, stored on the returned document.

        Returns:
            ParsedDocument with raw_text_by_page populated (1-indexed).
            sections and raw_text_by_section are empty — populated by SectionDetector.

        Raises:
            FileNotFoundError: If the PDF file does not exist.
            ValueError:         If the file cannot be opened as a PDF.
        """
        path_str = str(self._file_path)

        if not self._file_path.exists():
            raise FileNotFoundError(f"PDF file not found: {path_str}")

        # Step 1: Hash
        raw_bytes = self._file_path.read_bytes()
        file_hash = self._compute_hash(raw_bytes)

        # Step 2: Open with PyMuPDF and detect type
        try:
            pdf = fitz.open(path_str)
        except Exception as exc:
            raise ValueError(f"Cannot open PDF '{path_str}': {exc}") from exc

        total_pages = len(pdf)

        try:
            is_native = self._is_text_native(pdf)
        except Exception:
            is_native = False

        # Step 3 or 4: Extract text
        if is_native:
            raw_text_by_page = self._extract_pymupdf(pdf)
            ocr_path_used = "PYMUPDF"
            overall_confidence = 1.0
            logger.info(
                "file_id=%s: text-native PDF detected (%d pages). Using PyMuPDF.",
                file_id,
                total_pages,
            )
        else:
            pdf.close()  # Close before passing path to subprocesses
            pdf = None
            logger.info(
                "file_id=%s: scanned PDF detected (%d pages). Using Tesseract at %d DPI.",
                file_id,
                total_pages,
                TESSERACT_INITIAL_DPI,
            )
            raw_text_by_page, overall_confidence = await self._extract_tesseract(
                path_str, total_pages, TESSERACT_INITIAL_DPI
            )
            ocr_path_used = "TESSERACT"

            if overall_confidence < LOW_CONFIDENCE_THRESHOLD:
                logger.warning(
                    "file_id=%s: Poor scan quality detected (confidence=%.2f). "
                    "Re-scanning at higher resolution is recommended. "
                    "Continuing with Tesseract output.",
                    file_id,
                    overall_confidence,
                )

        if pdf is not None:
            pdf.close()

        return ParsedDocument(
            file_id=file_id,
            file_hash=file_hash,
            total_pages=total_pages,
            ocr_path_used=ocr_path_used,
            raw_text_by_page=raw_text_by_page,
            overall_ocr_confidence=round(overall_confidence, 4),
            pdf_file_path=path_str,
        )

    # ── Step 1: Hash ───────────────────────────────────────────

    def _compute_hash(self, data: bytes) -> str:
        """Return the SHA-256 hex digest of the raw file bytes."""
        return hashlib.sha256(data).hexdigest()

    # ── Step 2: Text-native detection ─────────────────────────

    def _is_text_native(self, pdf: fitz.Document) -> bool:
        """
        Sample the first min(SAMPLE_PAGES, total_pages) pages.
        Return True if the average characters per page exceeds TEXT_NATIVE_THRESHOLD.
        """
        sample_count = min(SAMPLE_PAGES, len(pdf))
        if sample_count == 0:
            return False

        total_chars = 0
        for i in range(sample_count):
            text = pdf[i].get_text("text")
            total_chars += len(text.strip())

        avg_chars = total_chars / sample_count
        logger.debug(
            "Text-native detection: avg_chars_per_page=%.1f (threshold=%d)",
            avg_chars,
            TEXT_NATIVE_THRESHOLD,
        )
        return avg_chars > TEXT_NATIVE_THRESHOLD

    # ── Step 3: PyMuPDF extraction ─────────────────────────────

    def _extract_pymupdf(self, pdf: fitz.Document) -> dict[int, str]:
        """
        Extract text from every page using fitz.Page.get_text().

        Returns:
            1-indexed dict mapping page number → extracted text.
        """
        result: dict[int, str] = {}
        for page_num in range(len(pdf)):
            text = pdf[page_num].get_text("text")
            result[page_num + 1] = text
        return result

    # ── Step 4: Tesseract extraction ───────────────────────────

    async def _extract_tesseract(
        self,
        pdf_path: str,
        total_pages: int,
        dpi: int,
    ) -> tuple[dict[int, str], float]:
        """
        Scanned-PDF extraction with multiprocessing.

        Steps:
          1. Submit all pages to a ProcessPoolExecutor concurrently.
          2. Collect per-page (text, confidence).
          3. Compute overall_confidence = mean(page_confidences).
          4. Return ({page_num: text}, overall_confidence).
        """
        loop = asyncio.get_event_loop()
        worker = partial(_ocr_single_page_worker, pdf_path, dpi=dpi)

        # Use a ProcessPoolExecutor to bypass the GIL for CPU-bound OCR
        with ProcessPoolExecutor() as executor:
            futures = [
                loop.run_in_executor(executor, worker, page_num)
                for page_num in range(total_pages)
            ]
            page_results: list[tuple[int, str, float]] = await asyncio.gather(*futures)

        raw_text_by_page: dict[int, str] = {}
        confidences: list[float] = []

        for page_1indexed, text, conf in page_results:
            raw_text_by_page[page_1indexed] = text
            confidences.append(conf)

        overall_confidence = (
            sum(confidences) / len(confidences) if confidences else 0.0
        )

        logger.debug(
            "Tesseract extraction complete: %d pages, overall_confidence=%.3f",
            total_pages,
            overall_confidence,
        )

        return raw_text_by_page, overall_confidence
