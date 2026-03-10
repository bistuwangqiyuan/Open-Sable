"""
OCR skill for Open-Sable
Extract text from images and scanned PDFs.
Cross-platform: uses Tesseract OCR, EasyOCR, or PyMuPDF.
"""

import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)


class OCRSkill:
    """Optical Character Recognition,  extract text from images and scanned PDFs.

    Priority chain:
      1. EasyOCR  (GPU-accelerated, best accuracy, multi-language)
      2. Tesseract via pytesseract (lightweight, widely available)
      3. PyMuPDF (PDF-only, extracts embedded text + basic OCR)
    """

    def __init__(self, config):
        self.config = config
        self._engine: Optional[str] = None
        self._easyocr_reader = None

    async def initialize(self) -> bool:
        """Detect available OCR engine."""
        # 1. Try EasyOCR
        try:
            import easyocr  # noqa: F401
            self._engine = "easyocr"
            logger.info("OCRSkill initialized (EasyOCR engine)")
            return True
        except ImportError:
            pass

        # 2. Try Tesseract
        try:
            import pytesseract
            # Verify tesseract binary exists
            pytesseract.get_tesseract_version()
            self._engine = "tesseract"
            logger.info("OCRSkill initialized (Tesseract engine)")
            return True
        except Exception:
            pass

        # 3. Try PyMuPDF (PDF-only OCR)
        try:
            import fitz  # noqa: F401
            self._engine = "pymupdf"
            logger.info("OCRSkill initialized (PyMuPDF engine,  PDF only)")
            return True
        except ImportError:
            pass

        logger.warning(
            "OCRSkill: no OCR engine found. Install one of:\n"
            "  pip install easyocr          (best accuracy, GPU)\n"
            "  pip install pytesseract       (+ apt install tesseract-ocr)\n"
            "  pip install PyMuPDF           (PDF text extraction)"
        )
        return False

    async def extract_text(
        self,
        file_path: str,
        language: str = "en",
        pages: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Extract text from an image or PDF file.

        Args:
            file_path: Path to image (png, jpg, bmp, tiff) or PDF file.
            language: OCR language code (e.g. 'en', 'es', 'fr', 'de').
            pages: For PDFs, list of 0-indexed page numbers to process (default: all).
        """
        if not self._engine:
            return {
                "success": False,
                "error": "No OCR engine available. Install easyocr, pytesseract, or PyMuPDF.",
            }

        path = Path(file_path)
        if not path.exists():
            return {"success": False, "error": f"File not found: {file_path}"}

        ext = path.suffix.lower()

        try:
            if ext == ".pdf":
                return await self._ocr_pdf(path, language, pages)
            elif ext in (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"):
                return await self._ocr_image(path, language)
            else:
                return {"success": False, "error": f"Unsupported file type: {ext}. Use images or PDFs."}
        except Exception as e:
            logger.error(f"OCR failed: {e}")
            return {"success": False, "error": str(e)}

    async def _ocr_image(self, path: Path, language: str) -> Dict[str, Any]:
        """Run OCR on a single image file."""
        if self._engine == "easyocr":
            return await self._easyocr_image(path, language)
        elif self._engine == "tesseract":
            return await self._tesseract_image(path, language)
        else:
            return {"success": False, "error": "Image OCR requires easyocr or tesseract."}

    async def _easyocr_image(self, path: Path, language: str) -> Dict[str, Any]:
        import easyocr

        # Lazy-init reader (heavy on first call)
        lang_list = [language]
        if language != "en":
            lang_list.append("en")  # EasyOCR works better with en as secondary

        if self._easyocr_reader is None:
            self._easyocr_reader = easyocr.Reader(lang_list, gpu=True)

        results = self._easyocr_reader.readtext(str(path))
        text_lines = [r[1] for r in results]
        confidences = [r[2] for r in results]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

        return {
            "success": True,
            "text": "\n".join(text_lines),
            "engine": "easyocr",
            "lines": len(text_lines),
            "confidence": round(avg_conf, 3),
        }

    async def _tesseract_image(self, path: Path, language: str) -> Dict[str, Any]:
        import pytesseract
        from PIL import Image

        img = Image.open(str(path))
        text = pytesseract.image_to_string(img, lang=language)
        data = pytesseract.image_to_data(img, lang=language, output_type=pytesseract.Output.DICT)

        # Compute average confidence from non-empty entries
        confs = [int(c) for c, t in zip(data["conf"], data["text"]) if t.strip() and int(c) > 0]
        avg_conf = sum(confs) / len(confs) / 100.0 if confs else 0.0

        return {
            "success": True,
            "text": text.strip(),
            "engine": "tesseract",
            "lines": len(text.strip().splitlines()),
            "confidence": round(avg_conf, 3),
        }

    async def _ocr_pdf(
        self, path: Path, language: str, pages: Optional[List[int]]
    ) -> Dict[str, Any]:
        """Extract text from PDF pages."""
        # Try PyMuPDF first (fastest for PDFs with embedded text)
        try:
            import fitz

            doc = fitz.open(str(path))
            total_pages = len(doc)
            page_texts = []

            target_pages = pages if pages else range(total_pages)

            for pg_num in target_pages:
                if pg_num >= total_pages:
                    continue
                page = doc[pg_num]
                text = page.get_text("text")

                # If page has very little text, it might be a scanned page
                if len(text.strip()) < 20 and self._engine != "pymupdf":
                    # Try OCR on the page image
                    pix = page.get_pixmap(dpi=300)
                    img_bytes = pix.tobytes("png")
                    ocr_text = await self._ocr_image_bytes(img_bytes, language)
                    if ocr_text:
                        text = ocr_text

                page_texts.append(f"--- Page {pg_num + 1} ---\n{text.strip()}")

            doc.close()

            full_text = "\n\n".join(page_texts)
            return {
                "success": True,
                "text": full_text,
                "engine": f"pymupdf+{self._engine}",
                "pages_processed": len(page_texts),
                "total_pages": total_pages,
            }

        except ImportError:
            pass

        # Fallback: convert PDF pages to images and OCR each one
        # Requires pdf2image (poppler) or similar
        try:
            from pdf2image import convert_from_path

            images = convert_from_path(str(path), dpi=300)
            page_texts = []

            target_pages = pages if pages else range(len(images))
            for pg_num in target_pages:
                if pg_num >= len(images):
                    continue
                img = images[pg_num]
                # Save temp image and OCR it
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    img.save(tmp.name)
                    result = await self._ocr_image(Path(tmp.name), language)
                    Path(tmp.name).unlink(missing_ok=True)

                if result.get("success"):
                    page_texts.append(f"--- Page {pg_num + 1} ---\n{result['text']}")

            return {
                "success": True,
                "text": "\n\n".join(page_texts),
                "engine": self._engine,
                "pages_processed": len(page_texts),
            }

        except ImportError:
            return {
                "success": False,
                "error": "Install PyMuPDF or pdf2image to OCR PDFs: pip install PyMuPDF",
            }

    async def _ocr_image_bytes(self, img_bytes: bytes, language: str) -> Optional[str]:
        """OCR from raw image bytes (used for PDF page images)."""
        import tempfile
        from pathlib import Path as P

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(img_bytes)
            tmp_path = P(tmp.name)

        try:
            result = await self._ocr_image(tmp_path, language)
            return result.get("text", "") if result.get("success") else ""
        finally:
            tmp_path.unlink(missing_ok=True)
