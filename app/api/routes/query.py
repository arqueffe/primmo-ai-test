from pydantic import BaseModel, Field
from fastapi import APIRouter, Request

from app.services.graph_query import GraphQuery

router = APIRouter()


class QueryRequest(BaseModel):
    question: str
    dossier_id: str | None = None


class QueryResponse(BaseModel):
    answer: str
    strategy: str
    sources: list[dict] = Field(default_factory=list)
    metrics: dict = Field(default_factory=dict)
    ocr_warnings: list[str] = Field(default_factory=list)


async def _run_query(question: str, request: Request) -> QueryResponse:
    graph_store = request.app.state.graph_store
    kg = request.app.state.kg
    api_key = request.app.state.api_key
    answer = await GraphQuery.query_graph(
        query=question,
        graph_store=graph_store,
        kg=kg,
        api_key=api_key,
    )
    if answer is None:
        answer = "No graph loaded yet. Ingest documents first."
    return QueryResponse(
        answer=answer,
        strategy="GRAPH_LOOKUP",
        sources=[],
        metrics={},
        ocr_warnings=[],
    )

@router.post("")
async def query(payload: QueryRequest, request: Request) -> QueryResponse:
    return await _run_query(payload.question, request)


@router.get("")
async def query_get(request: Request, query: str) -> QueryResponse:
    return await _run_query(query, request)