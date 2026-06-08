from enum import Enum
import uuid
from kg_gen import KGGen
from pydantic import BaseModel
from fastapi import UploadFile

from app.services.graph_builder import GraphBuilder
from app.services.graph_store import GraphStore
from app.services.ocr_extractor import OCRExtractor


class JobStatus(Enum):
    IN_PROGRESS = 1
    COMPLETED = 2
    FAILED = 3


class IngestJobResponse(BaseModel):
    job_id: str
    status: JobStatus
    error_message: str | None = None


class Ingestor:
    def __init__(self):
        self.job_store = {}

    async def submit(
        self, file: UploadFile, dossier_id: str, graph_store: GraphStore, kg: KGGen
    ) -> IngestJobResponse:
        job_id = uuid.uuid4().hex
        self.job_store[job_id] = IngestJobResponse(
            job_id=job_id, status=JobStatus.IN_PROGRESS
        )
        # Parse the document, potential failure from bad OCR document
        try:
            parsed_document = OCRExtractor.extract_text_from_ocr(file, dossier_id)
        except Exception as e:
            return self.fail_job(job_id, f"Error extracting text from OCR: {e}")
        # Build the graph from the document, potential failure from API call or more
        try:
            document_graph = await GraphBuilder.build_graph(parsed_document, kg)
        except Exception as e:
            return self.fail_job(job_id, f"Error building graph: {e}")
        # Recover the graph
        current_graph = graph_store.graph
        if current_graph is None:
            graph_store.update_graph(document_graph)
        else:
            # Aggregate the graphs
            aggregated_graph = await GraphBuilder.aggregate_graphs(
                [current_graph, document_graph], kg
            )
            graph_store.update_graph(aggregated_graph)
        return self.complete_job(job_id)

    def fail_job(self, job_id: str, error_message: str):
        if job_id in self.job_store:
            self.job_store[job_id] = IngestJobResponse(
                job_id=job_id, status=JobStatus.FAILED, error_message=error_message
            )
        else:
            raise ValueError(f"Job ID {job_id} not found.")
        return self.job_store[job_id]

    def complete_job(self, job_id: str):
        if job_id in self.job_store:
            self.job_store[job_id] = IngestJobResponse(
                job_id=job_id, status=JobStatus.COMPLETED
            )
        else:
            raise ValueError(f"Job ID {job_id} not found.")
        return self.job_store[job_id]

    def status(self, job_id: str) -> IngestJobResponse:
        if job_id not in self.job_store:
            raise ValueError(f"Job ID {job_id} not found.")
        return self.job_store[job_id]
