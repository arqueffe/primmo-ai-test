from typing import Annotated

from fastapi import APIRouter, Form, Request, UploadFile, status
from app.services.ingestor import Ingestor, IngestJobResponse

router = APIRouter()
ingestor = Ingestor()

@router.post(
    "/",
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_ingest_job(
    file: UploadFile,
    request: Request,
    dossier_id: Annotated[str, Form(...)],
) -> IngestJobResponse:
    graph_store = request.app.state.graph_store
    document_store = request.app.state.document_store
    metrics_store = request.app.state.metrics_store
    kg = request.app.state.kg
    job = await ingestor.submit(
        file=file,
        dossier_id=dossier_id,
        graph_store=graph_store,
        document_store=document_store,
        metrics_store=metrics_store,
        kg=kg,
    )
    return job
    
@router.get("/status/{job_id}")
def get_ingest_status(job_id: str) -> IngestJobResponse:
    return ingestor.status(job_id)

