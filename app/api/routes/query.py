from pydantic import BaseModel, Field
from fastapi import APIRouter, Request

from app.services.graph_query import CHAT_MODEL, GraphQuery

router = APIRouter()
QUERY_STRATEGY = "KG_AGENT"


class QueryRequest(BaseModel):
    question: str
    dossier_id: str | None = None


class QueryResponse(BaseModel):
    answer: str
    strategy: str
    sources: list[dict] = Field(default_factory=list)
    metrics: dict = Field(default_factory=dict)
    ocr_warnings: list[str] = Field(default_factory=list)


async def _run_query(
    question: str,
    request: Request,
    dossier_id: str | None = None,
) -> QueryResponse:
    graph_store = request.app.state.graph_store
    document_store = request.app.state.document_store
    metrics_store = request.app.state.metrics_store
    kg = request.app.state.kg
    api_key = request.app.state.api_key
    trace_enabled = bool(getattr(request.app.state, "agent_tracing_enabled", False))
    trace_dir = getattr(request.app.state, "agent_traces_dir", None)
    result = await GraphQuery.query_graph(
        query=question,
        graph_store=graph_store,
        document_store=document_store,
        kg=kg,
        api_key=api_key,
        trace_enabled=trace_enabled,
        trace_dir=trace_dir,
        trace_context={
            "request_method": request.method,
            "request_path": str(request.url.path),
            "client_host": request.client.host if request.client else None,
        },
    )

    if result is None:
        if dossier_id:
            answer = f"No graph loaded for dossier '{dossier_id}'. Ingest documents first."
        else:
            answer = "No graph loaded yet. Ingest documents first."
        return QueryResponse(
            answer=answer,
            strategy=QUERY_STRATEGY,
            sources=[],
            metrics={},
            ocr_warnings=[],
        )

    metrics_store.record_query_execution(
        question=question,
        dossier_id=None,
        strategy=QUERY_STRATEGY,
        model=CHAT_MODEL,
        metrics=result.metrics,
    )

    return QueryResponse(
        answer=result.answer,
        strategy=QUERY_STRATEGY,
        sources=[],
        metrics=result.metrics,
        ocr_warnings=[],
    )

@router.post("")
async def query(payload: QueryRequest, request: Request) -> QueryResponse:
    return await _run_query(payload.question, request, payload.dossier_id)


@router.get("")
async def query_get(
    request: Request,
    query: str,
    dossier_id: str | None = None,
) -> QueryResponse:
    return await _run_query(query, request, dossier_id)