from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def list_dossiers() -> dict[str, list[str]]:
    # TODO: Implement actual logic to list dossiers and their documents
    return {
        "dossier_1": ["doc1.pdf", "doc2.pdf"],
        "dossier_2": ["doc3.pdf", "doc4.pdf"],
    }