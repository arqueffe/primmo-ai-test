from dataclasses import dataclass
from time import perf_counter

from kg_gen import KGGen
from openai import OpenAI

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
        kg: KGGen,
        api_key: str,
        dossier_id: str | None = None,
    ) -> QueryExecutionResult | None:
        query_start = perf_counter()

        graph = graph_store.get_graph(dossier_id)
        if graph is None:
            return None

        graph_nx = KGGen.to_nx(graph)

        embedding_start = perf_counter()
        node_embeddings, _ = kg.generate_embeddings(graph_nx)
        embedding_latency_ms = (perf_counter() - embedding_start) * 1000

        retrieval_start = perf_counter()
        top_nodes, context, context_text = kg.retrieve(
            query=query,
            node_embeddings=node_embeddings,
            graph=graph_nx,
        )
        retrieval_latency_ms = (perf_counter() - retrieval_start) * 1000

        client = OpenAI(api_key=api_key)
        chat_start = perf_counter()
        response = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": f"Answer the following question based on the context: {context_text}"},
                {"role": "user", "content": f"Question: {query}"}
            ]
        )
        chat_latency_ms = (perf_counter() - chat_start) * 1000

        usage = getattr(response, "usage", None)
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        total_tokens = int(getattr(usage, "total_tokens", prompt_tokens + completion_tokens) or 0)

        total_latency_ms = (perf_counter() - query_start) * 1000
        cost_usd = MetricsStore.estimate_cost_usd(
            CHAT_MODEL,
            prompt_tokens,
            completion_tokens,
        )

        return QueryExecutionResult(
            answer=response.choices[0].message.content or "",
            metrics={
                "latency_ms": float(total_latency_ms),
                "embedding_latency_ms": float(embedding_latency_ms),
                "retrieval_latency_ms": float(retrieval_latency_ms),
                "chat_latency_ms": float(chat_latency_ms),
                "retrieved_nodes": len(top_nodes),
                "context_statements": len(context),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "cost_usd": float(cost_usd),
            },
        )