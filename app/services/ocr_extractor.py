import json
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
    def extract_text_from_ocr(file: UploadFile, dossier_id: str) -> ParsedDocument:
        if file.filename is None:
            raise ValueError("Uploaded file must have a filename.")
        try:
            data = json.load(file.file)
        except Exception as e:
            raise ValueError(f"Error reading uploaded file: {e}")
        
        text = data.get("responses", [{}])[0].get("fullTextAnnotation", {}).get("text", "")
        page_count = len(
            data.get("responses", [{}])[0].get("fullTextAnnotation", {}).get("pages", 0)
        )
        avg_confidence = sum(
            page.get("confidence", 0.0)
            for page in data.get("responses", [{}])[0]
            .get("fullTextAnnotation", {})
            .get("pages", [])
        ) / max(page_count, 1)
        
        if text == "":
            raise ValueError("No text found in the uploaded OCR file.")

        return ParsedDocument(
            text=text,
            file_name=file.filename,
            dossier_id=dossier_id,
            avg_confidence=avg_confidence,
            page_count=page_count,
        )
        