from fastapi import APIRouter

from app.api.routes.dossiers import router as dossiers_router
from app.api.routes.graph import router as graph_router
from app.api.routes.ingest import router as ingest_router
from app.api.routes.query import router as query_router

api_router = APIRouter()
api_router.include_router(dossiers_router, prefix="/dossiers", tags=["dossiers"])
api_router.include_router(graph_router, prefix="/graph", tags=["graph"])
api_router.include_router(ingest_router, prefix="/ingest", tags=["ingest"])
api_router.include_router(query_router, prefix="/query", tags=["query"])