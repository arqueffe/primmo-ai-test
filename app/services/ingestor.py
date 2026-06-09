from enum import Enum
from time import perf_counter
import uuid
from kg_gen import KGGen
from pydantic import BaseModel
from fastapi import UploadFile

from app.services.graph_builder import GraphBuilder
from app.services.document_store import DocumentStore
from app.services.graph_store import GraphStore
from app.services.metrics_store import MetricsStore
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
        self,
        file: UploadFile,
        dossier_id: str,
        graph_store: GraphStore,
        document_store: DocumentStore,
        metrics_store: MetricsStore,
        kg: KGGen,
    ) -> IngestJobResponse:
        ingest_start = perf_counter()
        job_id = uuid.uuid4().hex
        self.job_store[job_id] = IngestJobResponse(
            job_id=job_id, status=JobStatus.IN_PROGRESS
        )

        parse_start = perf_counter()
        # Persist uploaded source document for reload across server restarts.
        try:
            saved_path = document_store.save_upload(file=file, dossier_id=dossier_id)
        except Exception as e:
            return self.fail_job(job_id, f"Error saving uploaded document: {e}")

        # Parse the document, potential failure from bad OCR document.
        try:
            parsed_document = OCRExtractor.extract_text_from_file(saved_path, dossier_id)
        except Exception as e:
            return self.fail_job(job_id, f"Error extracting text from OCR: {e}")
        parse_latency_ms = (perf_counter() - parse_start) * 1000

        # Build the graph from the document, potential failure from API call or more
        kg.reset_token_usage()
        generation_start = perf_counter()
        try:
            document_graph = await GraphBuilder.build_graph(parsed_document, kg)
        except Exception as e:
            return self.fail_job(job_id, f"Error building graph: {e}")
        generation_latency_ms = (perf_counter() - generation_start) * 1000
        generation_tokens = kg.extract_token_usage_from_history()
        metrics_store.record_operation(
            name="kg_generation",
            category="ingest",
            latency_ms=generation_latency_ms,
            token_usage=generation_tokens,
            model=kg.model,
            metadata={
                "job_id": job_id,
                "dossier_id": dossier_id,
                "file_name": parsed_document.file_name,
            },
        )

        # Update per-dossier graph first, then refresh global cross-dossier view.
        kg.reset_token_usage()
        dossier_aggregation_start = perf_counter()
        graph_store.update_dossier_graph(
            dossier_id=dossier_id,
            document_graph=document_graph,
            kg=kg,
        )
        dossier_aggregation_latency_ms = (perf_counter() - dossier_aggregation_start) * 1000
        dossier_aggregation_tokens = kg.extract_token_usage_from_history()
        metrics_store.record_operation(
            name="kg_aggregation_dossier",
            category="ingest",
            latency_ms=dossier_aggregation_latency_ms,
            token_usage=dossier_aggregation_tokens,
            model=kg.model,
            metadata={
                "job_id": job_id,
                "dossier_id": dossier_id,
            },
        )

        kg.reset_token_usage()
        global_aggregation_start = perf_counter()
        graph_store.rebuild_global_graph(kg)
        global_aggregation_latency_ms = (perf_counter() - global_aggregation_start) * 1000
        global_aggregation_tokens = kg.extract_token_usage_from_history()
        metrics_store.record_operation(
            name="kg_aggregation_global",
            category="ingest",
            latency_ms=global_aggregation_latency_ms,
            token_usage=global_aggregation_tokens,
            model=kg.model,
            metadata={
                "job_id": job_id,
                "dossier_id": dossier_id,
            },
        )

        metrics_store.record_operation(
            name="ingest_total",
            category="ingest",
            latency_ms=(perf_counter() - ingest_start) * 1000,
            metadata={
                "job_id": job_id,
                "dossier_id": dossier_id,
                "file_name": parsed_document.file_name,
            },
        )
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
