from __future__ import annotations

import json
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Literal

from kg_gen import KGGen, Graph
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, SecretStr

from app.services.ocr_extractor import ParsedDocument


class KgJudgeEvaluation(BaseModel):
    verdict: Literal["pass", "needs_review", "fail"]
    score: float = Field(ge=0.0, le=1.0)
    summary: str = Field(min_length=1)
    strengths: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    document_text_truncated: bool = False
    graph_truncated: bool = False


@dataclass
class KgJudgeRunResult:
    evaluation: KgJudgeEvaluation
    latency_ms: float
    token_usage: dict[str, int]
    model: str


class KgJudgeService:
    MAX_DOCUMENT_CHARS = 18000
    MAX_GRAPH_CHARS = 12000
    SYSTEM_PROMPT = (
        "You are judging a knowledge graph extracted from a source document. "
        "Compare the graph against the document text and assess whether the graph was built properly. "
        "Prefer factual faithfulness over exhaustiveness. Mark pass only when the graph is broadly faithful and useful, "
        "needs_review when there are notable omissions or a few unsupported items, and fail when the graph contains major "
        "unsupported claims or misses critical facts. Keep the summary concise and actionable."
    )

    @classmethod
    def evaluate(
        cls,
        *,
        document: ParsedDocument,
        graph: Graph,
        model: str,
        api_key: str | None,
    ) -> KgJudgeRunResult:
        prepared_document, document_truncated = cls._truncate_middle(
            document.text,
            cls.MAX_DOCUMENT_CHARS,
        )
        serialized_graph = json.dumps(
            cls._to_json_compatible(KGGen.to_dict(graph)),
            ensure_ascii=False,
            indent=2,
        )
        prepared_graph, graph_truncated = cls._truncate_middle(
            serialized_graph,
            cls.MAX_GRAPH_CHARS,
        )

        llm = ChatOpenAI(
            model=cls._normalize_model_name(model),
            temperature=0.0,
            api_key=SecretStr(api_key) if api_key else None,
        )
        judge = llm.with_structured_output(KgJudgeEvaluation, include_raw=True)

        started_at = perf_counter()
        judge_result = judge.invoke(
            [
                SystemMessage(content=cls.SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        "Evaluate this extracted knowledge graph against the source document.\n\n"
                        f"Document metadata:\n- file_name: {document.file_name}\n"
                        f"- dossier_id: {document.dossier_id}\n"
                        f"- page_count: {document.page_count}\n"
                        f"- avg_confidence: {document.avg_confidence}\n\n"
                        f"Document text (truncated={str(document_truncated).lower()}):\n"
                        f"<document>\n{prepared_document}\n</document>\n\n"
                        f"Knowledge graph JSON (truncated={str(graph_truncated).lower()}):\n"
                        f"<graph>\n{prepared_graph}\n</graph>\n\n"
                        "Return a verdict, a score between 0 and 1, a short summary, a few strengths, and the main issues."
                    )
                ),
            ]
        )
        latency_ms = (perf_counter() - started_at) * 1000

        evaluation = judge_result.get("parsed")
        if evaluation is None:
            parsing_error = judge_result.get("parsing_error")
            raise RuntimeError(f"KG judge failed to produce a valid evaluation: {parsing_error}")

        evaluation.document_text_truncated = document_truncated
        evaluation.graph_truncated = graph_truncated

        raw_message = judge_result.get("raw")
        prompt_tokens, completion_tokens, total_tokens = cls._extract_usage(
            [raw_message] if raw_message is not None else []
        )
        return KgJudgeRunResult(
            evaluation=evaluation,
            latency_ms=float(latency_ms),
            token_usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
            model=model,
        )

    @staticmethod
    def _normalize_model_name(model: str) -> str:
        if model.startswith("openai/"):
            return model.split("/", 1)[1]
        return model

    @staticmethod
    def _truncate_middle(value: str, max_chars: int) -> tuple[str, bool]:
        if len(value) <= max_chars:
            return value, False

        segment_len = max_chars // 2
        truncated = (
            f"{value[:segment_len]}\n\n...<truncated for judge>...\n\n"
            f"{value[-segment_len:]}"
        )
        return truncated, True

    @classmethod
    def _to_json_compatible(cls, value: Any) -> Any:
        if isinstance(value, set):
            return sorted(cls._to_json_compatible(item) for item in value)
        if isinstance(value, dict):
            return {
                key: cls._to_json_compatible(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [cls._to_json_compatible(item) for item in value]
        if isinstance(value, tuple):
            return [cls._to_json_compatible(item) for item in value]
        return value

    @staticmethod
    def _extract_usage(messages: list[Any]) -> tuple[int, int, int]:
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0

        for message in messages:
            if not isinstance(message, AIMessage):
                continue

            usage_metadata = getattr(message, "usage_metadata", None) or {}
            prompt = int(
                usage_metadata.get("input_tokens")
                or usage_metadata.get("prompt_tokens")
                or 0
            )
            completion = int(
                usage_metadata.get("output_tokens")
                or usage_metadata.get("completion_tokens")
                or 0
            )
            total = int(usage_metadata.get("total_tokens") or (prompt + completion))

            if prompt == 0 and completion == 0 and total == 0:
                response_metadata = getattr(message, "response_metadata", None) or {}
                token_usage = response_metadata.get("token_usage", {})
                prompt = int(token_usage.get("prompt_tokens", 0) or 0)
                completion = int(token_usage.get("completion_tokens", 0) or 0)
                total = int(token_usage.get("total_tokens", prompt + completion) or 0)

            prompt_tokens += prompt
            completion_tokens += completion
            total_tokens += total

        return prompt_tokens, completion_tokens, total_tokens