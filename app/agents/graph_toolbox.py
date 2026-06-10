from __future__ import annotations

from time import perf_counter
from typing import Any, Literal

import networkx as nx
from kg_gen import KGGen, Graph
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from app.agents.graph_tool_logic import GraphToolLogic
from app.services.document_store import DocumentStore

MAX_TOOL_ITEMS = 20
MAX_CONTEXT_STATEMENTS = 40
MAX_LIST_ITEMS = 200


class ExactEntityLookupInput(BaseModel):
    exact_name: str = Field(min_length=1)
    dossier_id: str | None = None


class RelationFilterInput(BaseModel):
    predicate: str | None = None
    entity: str | None = None
    limit: int = Field(default=10, ge=1, le=MAX_TOOL_ITEMS)
    dossier_id: str | None = None


class NeighborTraversalInput(BaseModel):
    entity: str = Field(min_length=1)
    depth: int = Field(default=2, ge=1, le=3)
    limit: int = Field(default=20, ge=1, le=MAX_CONTEXT_STATEMENTS)
    dossier_id: str | None = None


class NodeIncidentEdgesInput(BaseModel):
    entity: str = Field(min_length=1)
    direction: Literal["in", "out", "both"] = "both"
    limit: int = Field(default=20, ge=1, le=MAX_CONTEXT_STATEMENTS)
    dossier_id: str | None = None


class SemanticRetrieveInput(BaseModel):
    query: str = Field(min_length=1)
    k: int = Field(default=8, ge=1, le=12)
    dossier_id: str | None = None


class EntityListInput(BaseModel):
    limit: int = Field(default=50, ge=1, le=MAX_LIST_ITEMS)
    offset: int = Field(default=0, ge=0)
    dossier_id: str | None = None


class RelationListInput(BaseModel):
    limit: int = Field(default=50, ge=1, le=MAX_LIST_ITEMS)
    offset: int = Field(default=0, ge=0)
    dossier_id: str | None = None


class DossierCatalogInput(BaseModel):
    limit: int = Field(default=50, ge=1, le=MAX_LIST_ITEMS)
    offset: int = Field(default=0, ge=0)


class DocumentCatalogInput(BaseModel):
    dossier_id: str | None = None


class DocumentEvidenceSearchInput(BaseModel):
    query: str = Field(min_length=1)
    dossier_id: str | None = None
    document_name: str | None = None
    limit: int = Field(default=5, ge=1, le=MAX_TOOL_ITEMS)


class EvidenceSubgraphInput(BaseModel):
    query: str = Field(min_length=1)
    dossier_id: str | None = None
    k: int = Field(default=6, ge=1, le=MAX_TOOL_ITEMS)
    per_entity_edge_limit: int = Field(default=6, ge=1, le=MAX_CONTEXT_STATEMENTS)
    include_documents: bool = True


class GraphToolbox(GraphToolLogic):
    def __init__(
        self,
        *,
        graph: Graph,
        kg: KGGen,
        document_store: DocumentStore | None = None,
    ) -> None:
        self._graph = graph
        self._kg = kg
        self._document_store = document_store
        self._graph_cache: dict[str, nx.DiGraph] = {}
        self._embedding_cache: dict[str, dict[str, Any]] = {}
        self._document_text_cache: dict[str, str] = {}

        self.embedding_latency_ms = 0.0
        self.retrieval_latency_ms = 0.0
        self.retrieved_nodes = 0
        self.context_statements = 0
        self.tool_calls = 0
        self.tool_calls_by_name: dict[str, int] = {}
        self.tool_latency_ms_by_name: dict[str, float] = {}

    @property
    def graph_prepare_latency_ms(self) -> float:
        return self._ensure_scope_graph(None)[1]

    def get_scope_graph(self, scope: str | None = None) -> nx.DiGraph:
        resolved_scope = self.normalize_dossier_id(scope)
        return self._ensure_scope_graph(resolved_scope)[0]

    def build_tools(self) -> list[BaseTool]:
        @tool("dossier_catalog", args_schema=DossierCatalogInput)
        def dossier_catalog_tool(limit: int = 50, offset: int = 0) -> dict[str, Any]:
            """List known dossier IDs with graph coverage and document counts."""
            start = perf_counter()
            result = self._dossier_catalog(limit=limit, offset=offset)
            self._record_tool_call("dossier_catalog", start)
            return result

        @tool("document_catalog", args_schema=DocumentCatalogInput)
        def document_catalog_tool(dossier_id: str | None = None) -> dict[str, Any]:
            """List persisted source documents for one dossier or for all dossiers."""
            start = perf_counter()
            result = self._document_catalog(dossier_id=dossier_id)
            self._record_tool_call("document_catalog", start)
            return result

        @tool("document_evidence_search", args_schema=DocumentEvidenceSearchInput)
        def document_evidence_search_tool(
            query: str,
            dossier_id: str | None = None,
            document_name: str | None = None,
            limit: int = 5,
        ) -> dict[str, Any]:
            """Search OCR text for matching evidence snippets across one dossier or all dossiers."""
            start = perf_counter()
            result = self._document_evidence_search(
                query=query,
                dossier_id=dossier_id,
                document_name=document_name,
                limit=limit,
            )
            self._record_tool_call("document_evidence_search", start)
            return result

        @tool("evidence_subgraph", args_schema=EvidenceSubgraphInput)
        def evidence_subgraph_tool(
            query: str,
            dossier_id: str | None = None,
            k: int = 6,
            per_entity_edge_limit: int = 6,
            include_documents: bool = True,
        ) -> dict[str, Any]:
            """Gather evidence-first graph anchors for a natural-language question before any exact entity lookup."""
            start = perf_counter()
            result = self._evidence_subgraph(
                query=query,
                dossier_id=dossier_id,
                k=k,
                per_entity_edge_limit=per_entity_edge_limit,
                include_documents=include_documents,
            )
            self._record_tool_call("evidence_subgraph", start)
            return result

        @tool("entity_list", args_schema=EntityListInput)
        def entity_list_tool(
            limit: int = 50,
            offset: int = 0,
            dossier_id: str | None = None,
        ) -> dict[str, Any]:
            """List entities in the graph, optionally scoped by dossier."""
            start = perf_counter()
            result = self._entity_list(limit=limit, offset=offset, dossier_id=dossier_id)
            self._record_tool_call("entity_list", start)
            return result

        @tool("relation_list", args_schema=RelationListInput)
        def relation_list_tool(
            limit: int = 50,
            offset: int = 0,
            dossier_id: str | None = None,
        ) -> dict[str, Any]:
            """List relations in the graph, optionally scoped by dossier."""
            start = perf_counter()
            result = self._relation_list(limit=limit, offset=offset, dossier_id=dossier_id)
            self._record_tool_call("relation_list", start)
            return result

        @tool("exact_entity_lookup", args_schema=ExactEntityLookupInput)
        def exact_entity_lookup_tool(exact_name: str, dossier_id: str | None = None) -> dict[str, Any]:
            """Look up one entity by exact surface form only. Do not use for generic nouns, roles, or guesses."""
            start = perf_counter()
            result = self._exact_entity_lookup(exact_name=exact_name, dossier_id=dossier_id)
            self._record_tool_call("exact_entity_lookup", start)
            return result

        @tool("relation_filter", args_schema=RelationFilterInput)
        def relation_filter_tool(
            predicate: str | None = None,
            entity: str | None = None,
            limit: int = 10,
            dossier_id: str | None = None,
        ) -> dict[str, Any]:
            """Filter graph relations by substring match on predicate text and/or endpoint text."""
            start = perf_counter()
            result = self._relation_filter(
                predicate=predicate,
                entity=entity,
                limit=limit,
                dossier_id=dossier_id,
            )
            self._record_tool_call("relation_filter", start)
            return result

        @tool("neighbor_traversal", args_schema=NeighborTraversalInput)
        def neighbor_traversal_tool(
            entity: str,
            depth: int = 2,
            limit: int = 20,
            dossier_id: str | None = None,
        ) -> dict[str, Any]:
            """Traverse neighbors for an exact entity string and return contextual statements."""
            start = perf_counter()
            result = self._neighbor_traversal(
                entity=entity,
                depth=depth,
                limit=limit,
                dossier_id=dossier_id,
            )
            self._record_tool_call("neighbor_traversal", start)
            return result

        @tool("node_incident_edges", args_schema=NodeIncidentEdgesInput)
        def node_incident_edges_tool(
            entity: str,
            direction: Literal["in", "out", "both"] = "both",
            limit: int = 20,
            dossier_id: str | None = None,
        ) -> dict[str, Any]:
            """Inspect incident edges for an exact entity string with optional dossier scope."""
            start = perf_counter()
            result = self._node_incident_edges(
                entity=entity,
                direction=direction,
                limit=limit,
                dossier_id=dossier_id,
            )
            self._record_tool_call("node_incident_edges", start)
            return result

        @tool("semantic_retrieve", args_schema=SemanticRetrieveInput)
        def semantic_retrieve_tool(
            query: str,
            k: int = 8,
            dossier_id: str | None = None,
        ) -> dict[str, Any]:
            """Run semantic retrieval over the graph and return candidate entities plus evidence context."""
            start = perf_counter()
            result = self._semantic_retrieve(query=query, k=k, dossier_id=dossier_id)
            self._record_tool_call("semantic_retrieve", start)
            return result

        return [
            dossier_catalog_tool,
            document_catalog_tool,
            document_evidence_search_tool,
            evidence_subgraph_tool,
            entity_list_tool,
            semantic_retrieve_tool,
            exact_entity_lookup_tool,
            relation_list_tool,
            node_incident_edges_tool,
            relation_filter_tool,
            neighbor_traversal_tool,
        ]

    def _record_tool_call(self, name: str, start: float) -> None:
        elapsed_ms = (perf_counter() - start) * 1000
        self.tool_calls += 1
        self.tool_calls_by_name[name] = self.tool_calls_by_name.get(name, 0) + 1
        self.tool_latency_ms_by_name[name] = self.tool_latency_ms_by_name.get(name, 0.0) + float(elapsed_ms)
