from fastapi import APIRouter, Request

router = APIRouter()

@router.get("/")
def get_graph(request: Request, dossier_id: str | None = None) -> dict:
    graph_store = request.app.state.graph_store
    return graph_store.to_dict(dossier_id=dossier_id)