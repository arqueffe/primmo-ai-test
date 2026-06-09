from typing import Any

from fastapi import APIRouter, Request

router = APIRouter()

@router.get("/")
def list_dossiers(request: Request) -> list[dict[str, Any]]:
    document_store = request.app.state.document_store
    return document_store.list_dossiers()