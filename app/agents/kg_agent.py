from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

from kg_gen import KGGen, Graph
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field, SecretStr

from app.agents.graph_toolbox import GraphToolbox
from app.agents.tracing import AgentTraceRecorder
from app.services.document_store import DocumentStore

CHAT_MODEL = "gpt-5.4-mini"
MAX_AGENT_RECURSION_LIMIT = 8


class AgentExecutionPlan(BaseModel):
    question_type: Literal[
        "exact_entity",
        "role_lookup",
        "transaction_lookup",
        "document_lookup",
        "inconsistency_check",
        "missing_pieces_summary",
        "general_lookup",
    ]
    first_tool: Literal[
        "evidence_subgraph",
        "exact_entity_lookup",
        "dossier_catalog",
        "document_catalog",
        "document_evidence_search",
        "semantic_retrieve",
    ]
    scope_strategy: Literal[
        "global_first",
        "dossier_first",
        "cross_dossier",
        "document_first",
    ]
    exact_entity_lookup_allowed: bool
    exact_entity_lookup_rule: str = Field(min_length=1)
    answer_requirements: list[str] = Field(default_factory=list)


@dataclass
class KnowledgeGraphAgentResult:
    answer: str
    metrics: dict[str, Any]


class KnowledgeGraphAgent:
    PLANNER_PROMPT = (
        "You are a query planner for a knowledge-graph agent. Choose the first tool and strategy for answering the "
        "question. Prefer evidence_subgraph for role, transaction, inconsistency, and document questions. Use "
        "exact_entity_lookup only when the question already contains an exact surface form or after another tool has "
        "returned exact entity candidates. Never use exact_entity_lookup for generic nouns, roles, or guessed names."
    )

    def __init__(
        self,
        *,
        kg: KGGen,
        api_key: str,
        model: str = CHAT_MODEL,
    ) -> None:
        self._kg = kg
        self._api_key = api_key
        self._model = model

    def run(
        self,
        *,
        query: str,
        graph: Graph,
        document_store: DocumentStore | None = None,
        trace_enabled: bool = False,
        trace_dir: Path | None = None,
        trace_context: dict[str, Any] | None = None,
    ) -> KnowledgeGraphAgentResult:
        query_start = perf_counter()
        trace_recorder: AgentTraceRecorder | None = None
        if trace_enabled and trace_dir is not None:
            trace_recorder = AgentTraceRecorder(
                trace_dir=Path(trace_dir),
                query=query,
                dossier_id=None,
                model=self._model,
                extra=trace_context,
            )

        toolbox = GraphToolbox(
            graph=graph,
            kg=self._kg,
            document_store=document_store,
        )
        graph_prepare_latency_ms = toolbox.graph_prepare_latency_ms
        if trace_recorder is not None:
            scope_graph = toolbox.get_scope_graph()
            trace_recorder.add_event(
                "graph_scope_ready",
                {
                    "nodes": int(scope_graph.number_of_nodes()),
                    "edges": int(scope_graph.number_of_edges()),
                    "graph_prepare_latency_ms": float(graph_prepare_latency_ms),
                },
            )

        llm = ChatOpenAI(
            model=self._model,
            api_key=SecretStr(self._api_key),
            temperature=0.0,
        )

        plan, planner_prompt_tokens, planner_completion_tokens, planner_total_tokens, planner_latency_ms = self._plan_execution(
            query=query,
            llm=llm,
        )
        if trace_recorder is not None:
            trace_recorder.add_event("agent_plan", plan.model_dump())

        agent = create_react_agent(
            model=llm,
            tools=toolbox.build_tools(),
            prompt=(
                "You are a knowledge graph assistant. Use the available tools to inspect the graph and answer only "
                "from tool evidence. Choose dossier scope, entity resolution, and search strategy through tool calls, "
                "not assumptions. Follow this planner output unless tool evidence forces you to revise it:\n"
                f"- question_type: {plan.question_type}\n"
                f"- first_tool: {plan.first_tool}\n"
                f"- scope_strategy: {plan.scope_strategy}\n"
                f"- exact_entity_lookup_allowed: {str(plan.exact_entity_lookup_allowed).lower()}\n"
                f"- exact_entity_lookup_rule: {plan.exact_entity_lookup_rule}\n"
                f"- answer_requirements: {', '.join(plan.answer_requirements) if plan.answer_requirements else 'return only evidence-backed conclusions'}\n"
                "Use evidence_subgraph before exact_entity_lookup for role, transaction, inconsistency, and document questions. "
                "An empty exact_entity_lookup is not evidence of absence. If the evidence is insufficient or conflicting, say so briefly and clearly."
            ),
        )

        run_start = perf_counter()
        invoke_config: RunnableConfig = {"recursion_limit": MAX_AGENT_RECURSION_LIMIT}
        if trace_recorder is not None:
            invoke_config["callbacks"] = [trace_recorder]

        try:
            result = agent.invoke(
                {
                    "messages": [
                        HumanMessage(content=query)
                    ]
                },
                config=invoke_config,
            )
        except Exception as exc:
            if trace_recorder is not None:
                trace_recorder.finalize(error=exc)
            raise
        chat_latency_ms = (perf_counter() - run_start) * 1000

        messages = result.get("messages", [])
        answer = self._extract_answer(messages)
        prompt_tokens, completion_tokens, total_tokens, agent_steps = self._extract_usage(messages)

        total_latency_ms = (perf_counter() - query_start) * 1000

        metrics = {
            "latency_ms": float(total_latency_ms),
            "planner_latency_ms": float(planner_latency_ms),
            "graph_prepare_latency_ms": float(graph_prepare_latency_ms),
            "embedding_latency_ms": float(toolbox.embedding_latency_ms),
            "retrieval_latency_ms": float(toolbox.retrieval_latency_ms),
            "chat_latency_ms": float(chat_latency_ms),
            "retrieved_nodes": int(toolbox.retrieved_nodes),
            "context_statements": int(toolbox.context_statements),
            "agent_steps": int(agent_steps),
            "tool_calls": int(toolbox.tool_calls),
            "tool_calls_by_name": dict(toolbox.tool_calls_by_name),
            "tool_latency_ms_by_name": {
                name: float(latency)
                for name, latency in toolbox.tool_latency_ms_by_name.items()
            },
            "prompt_tokens": int(prompt_tokens + planner_prompt_tokens),
            "completion_tokens": int(completion_tokens + planner_completion_tokens),
            "total_tokens": int(total_tokens + planner_total_tokens),
            "plan": plan.model_dump(),
        }

        if trace_recorder is not None:
            trace_file = trace_recorder.finalize(answer=answer, metrics=metrics)
            metrics["trace_file"] = trace_file

        return KnowledgeGraphAgentResult(
            answer=answer,
            metrics=metrics,
        )

    @staticmethod
    def _extract_answer(messages: list[Any]) -> str:
        for message in reversed(messages):
            if not isinstance(message, AIMessage):
                continue
            if getattr(message, "tool_calls", None):
                continue
            text = KnowledgeGraphAgent._content_to_text(message.content)
            if text:
                return text
        return "I could not determine an answer from the available graph data."

    @staticmethod
    def _content_to_text(content: Any) -> str:
        if isinstance(content, str):
            return content.strip()
        if not isinstance(content, list):
            return ""

        text_parts = [
            KnowledgeGraphAgent._content_part_to_text(part)
            for part in content
        ]
        merged = "\n".join(part for part in text_parts if part)
        return merged.strip()

    @staticmethod
    def _content_part_to_text(part: Any) -> str:
        if isinstance(part, str):
            return part.strip()
        if isinstance(part, dict) and part.get("type") == "text":
            return str(part.get("text", "")).strip()
        return ""

    @classmethod
    def _plan_execution(
        cls,
        *,
        query: str,
        llm: ChatOpenAI,
    ) -> tuple[AgentExecutionPlan, int, int, int, float]:
        planner = llm.with_structured_output(AgentExecutionPlan, include_raw=True)
        plan_start = perf_counter()
        planner_result = planner.invoke(
            [
                SystemMessage(content=cls.PLANNER_PROMPT),
                HumanMessage(
                    content=(
                        "Question: "
                        f"{query}\n"
                        "Available tools: evidence_subgraph, exact_entity_lookup, semantic_retrieve, dossier_catalog, "
                        "document_catalog, document_evidence_search, relation_list, node_incident_edges, relation_filter, neighbor_traversal."
                    )
                ),
            ]
        )
        planner_latency_ms = (perf_counter() - plan_start) * 1000

        plan = planner_result.get("parsed")
        if plan is None:
            parsing_error = planner_result.get("parsing_error")
            raise RuntimeError(f"Planner failed to produce a valid execution plan: {parsing_error}")

        raw_message = planner_result.get("raw")
        prompt_tokens, completion_tokens, total_tokens, _ = cls._extract_usage(
            [raw_message] if raw_message is not None else []
        )
        return plan, prompt_tokens, completion_tokens, total_tokens, float(planner_latency_ms)

    @staticmethod
    def _extract_usage(messages: list[Any]) -> tuple[int, int, int, int]:
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        agent_steps = 0

        for message in messages:
            if not isinstance(message, AIMessage):
                continue
            agent_steps += 1

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

        return prompt_tokens, completion_tokens, total_tokens, agent_steps
