from pathlib import Path
import shutil
from typing import Any

from fastapi import UploadFile


class DocumentStore:
    def __init__(self, root_dir: str | Path):
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def save_upload(self, file: UploadFile, dossier_id: str) -> Path:
        if not file.filename:
            raise ValueError("Uploaded file must have a filename.")

        safe_name = Path(file.filename).name
        if not safe_name:
            raise ValueError("Uploaded file has invalid filename.")

        dossier_dir = self.root_dir / dossier_id
        dossier_dir.mkdir(parents=True, exist_ok=True)
        target_path = dossier_dir / safe_name

        file.file.seek(0)
        with target_path.open("wb") as destination:
            shutil.copyfileobj(file.file, destination)
        file.file.seek(0)

        return target_path

    def list_dossiers(self) -> list[dict[str, Any]]:
        if not self.root_dir.exists() or not self.root_dir.is_dir():
            return []

        dossiers: list[dict[str, Any]] = []
        for dossier_dir in sorted(self.root_dir.iterdir(), key=lambda p: p.name):
            if not dossier_dir.is_dir():
                continue
            documents = sorted(
                [p.name for p in dossier_dir.iterdir() if p.is_file()],
                key=str.lower,
            )
            dossiers.append({
                "id": dossier_dir.name,
                "document_count": len(documents),
                "documents": documents,
            })

        return dossiers
