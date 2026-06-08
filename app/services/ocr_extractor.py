import json
from pathlib import Path
from fastapi import UploadFile
from dataclasses import dataclass

@dataclass
class ParsedDocument:
    text: str
    file_name: str
    dossier_id: str
    avg_confidence: float
    page_count: int

class OCRExtractor:

    @staticmethod
    def _extract_from_data(data: dict, file_name: str, dossier_id: str) -> ParsedDocument:
        response = data.get("responses", [{}])[0]
        full_text = response.get("fullTextAnnotation", {})
        pages = full_text.get("pages", [])
        text = full_text.get("text", "")

        page_count = len(pages)
        avg_confidence = (
            sum(page.get("confidence", 0.0) for page in pages) / max(page_count, 1)
        )

        if text == "":
            raise ValueError("No text found in the uploaded OCR file.")

        return ParsedDocument(
            text=text,
            file_name=file_name,
            dossier_id=dossier_id,
            avg_confidence=avg_confidence,
            page_count=page_count,
        )

    @staticmethod
    def extract_text_from_ocr(file: UploadFile, dossier_id: str) -> ParsedDocument:
        if file.filename is None:
            raise ValueError("Uploaded file must have a filename.")
        try:
            data = json.load(file.file)
        except Exception as e:
            raise ValueError(f"Error reading uploaded file: {e}")

        return OCRExtractor._extract_from_data(
            data=data,
            file_name=file.filename,
            dossier_id=dossier_id,
        )

    @staticmethod
    def extract_text_from_file(file_path: str | Path, dossier_id: str) -> ParsedDocument:
        path = Path(file_path)
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            raise ValueError(f"Error reading saved OCR file: {e}")

        return OCRExtractor._extract_from_data(
            data=data,
            file_name=path.name,
            dossier_id=dossier_id,
        )
        