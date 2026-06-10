from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kg_gen import KGGen

from app.agents import KnowledgeGraphAgent
from app.services.document_store import DocumentStore
from app.services.graph_store import GraphStore
from app.services.metrics_store import MetricsStore


@dataclass
class QueryExecutionResult:
    answer: str
    metrics: dict


CHAT_MODEL = "gpt-4o"


class GraphQuery:
    @staticmethod
    async def query_graph(
        query: str,
        graph_store: GraphStore,
        document_store: DocumentStore,
        kg: KGGen,
        api_key: str,
        trace_enabled: bool = False,
        trace_dir: Path | None = None,
        trace_context: dict[str, Any] | None = None,
    ) -> QueryExecutionResult | None:
        graph = graph_store.get_graph()
        if graph is None:
            return None

        agent = KnowledgeGraphAgent(
            kg=kg,
            api_key=api_key,
            model=CHAT_MODEL,
        )
        result = agent.run(
            query=query,
            graph=graph,
            document_store=document_store,
            trace_enabled=trace_enabled,
            trace_dir=trace_dir,
            trace_context=trace_context,
        )

        metrics = dict(result.metrics)
        prompt_tokens = int(metrics.get("prompt_tokens", 0) or 0)
        completion_tokens = int(metrics.get("completion_tokens", 0) or 0)
        total_tokens = int(metrics.get("total_tokens", prompt_tokens + completion_tokens) or 0)
        metrics["total_tokens"] = total_tokens
        metrics["cost_usd"] = float(
            MetricsStore.estimate_cost_usd(
                CHAT_MODEL,
                prompt_tokens,
                completion_tokens,
            )
        )

        return QueryExecutionResult(
            answer=result.answer,
            metrics=metrics,
        )
