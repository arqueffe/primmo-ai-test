from __future__ import annotations

from time import perf_counter
from typing import Any, Literal

import networkx as nx
from kg_gen import KGGen, Graph

from app.services.document_store import DocumentStore
from app.services.ocr_extractor import OCRExtractor

MAX_TOOL_ITEMS = 20
MAX_CONTEXT_STATEMENTS = 40
MAX_DOCUMENT_SNIPPET_CHARS = 280
MAX_EVIDENCE_EDGES_PER_ANCHOR = 6


class GraphToolLogic:
    _graph: Graph
    _kg: KGGen
    _document_store: DocumentStore | None
    _graph_cache: dict[str, nx.DiGraph]
    _embedding_cache: dict[str, dict[str, Any]]
    _document_text_cache: dict[str, str]

    @staticmethod
    def normalize_dossier_id(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _resolve_scope(self, requested_scope: str | None) -> tuple[str | None, str | None]:
        return self.normalize_dossier_id(requested_scope), None

    def _known_dossier_ids(self) -> list[str]:
        dossier_ids: set[str] = set()

        metadata = self._graph.entity_metadata or {}
        for values in metadata.values():
            for value in values or set():
                normalized = self.normalize_dossier_id(value)
                if normalized is not None:
                    dossier_ids.add(normalized)

        if self._document_store is not None:
            for dossier in self._document_store.list_dossiers():
                normalized = self.normalize_dossier_id(dossier.get("id"))
                if normalized is not None:
                    dossier_ids.add(normalized)

        return sorted(dossier_ids)

    def _dossier_catalog(self, *, limit: int, offset: int) -> dict[str, Any]:
        dossier_ids = self._known_dossier_ids()
        items = dossier_ids[offset:offset + limit]
        document_counts = {}
        if self._document_store is not None:
            document_counts = {
                str(item.get("id")): int(item.get("document_count", 0) or 0)
                for item in self._document_store.list_dossiers()
            }

        dossiers_payload = []
        for dossier_id in items:
            graph_nx, _ = self._ensure_scope_graph(dossier_id)
            dossiers_payload.append(
                {
                    "dossier_id": dossier_id,
                    "entity_count": int(graph_nx.number_of_nodes()),
                    "relation_count": int(graph_nx.number_of_edges()),
                    "document_count": int(document_counts.get(dossier_id, 0)),
                }
            )

        return {
            "total_count": len(dossier_ids),
            "count": len(dossiers_payload),
            "offset": offset,
            "limit": limit,
            "truncated": (offset + len(dossiers_payload)) < len(dossier_ids),
            "dossiers": dossiers_payload,
        }

    def _document_catalog(self, *, dossier_id: str | None) -> dict[str, Any]:
        requested_scope = self.normalize_dossier_id(dossier_id)
        if self._document_store is None:
            return {
                "count": 0,
                "dossiers": [],
            }

        dossiers = self._document_store.list_dossiers()
        if requested_scope is not None:
            dossiers = [item for item in dossiers if self.normalize_dossier_id(item.get("id")) == requested_scope]

        payload = [
            {
                "dossier_id": str(item.get("id", "")).strip(),
                "document_count": int(item.get("document_count", 0) or 0),
                "documents": list(item.get("documents", [])),
            }
            for item in dossiers
        ]

        return {
            "count": len(payload),
            "dossiers": payload,
        }

    @staticmethod
    def _tokenize_text(value: str) -> list[str]:
        cleaned_chars: list[str] = []
        for char in value.lower():
            cleaned_chars.append(char if char.isalnum() else " ")
        tokens = [token for token in "".join(cleaned_chars).split() if token]
        return tokens

    @staticmethod
    def _build_document_snippet(text: str, query_tokens: list[str]) -> str:
        normalized_text = text.lower()
        match_positions = [normalized_text.find(token) for token in query_tokens if token]
        match_positions = [position for position in match_positions if position >= 0]
        start = max(0, (min(match_positions) if match_positions else 0) - 120)
        end = min(len(text), start + MAX_DOCUMENT_SNIPPET_CHARS)
        snippet = " ".join(text[start:end].split())
        return snippet

    def _load_document_text(self, dossier_id: str, document_path: Any) -> str:
        cache_key = f"{dossier_id}:{getattr(document_path, 'name', str(document_path))}"
        cached = self._document_text_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            parsed = OCRExtractor.extract_text_from_file(document_path, dossier_id)
            text = parsed.text
        except Exception:
            text = ""

        self._document_text_cache[cache_key] = text
        return text

    def _document_evidence_search(
        self,
        *,
        query: str,
        dossier_id: str | None,
        document_name: str | None,
        limit: int,
    ) -> dict[str, Any]:
        requested_scope = self.normalize_dossier_id(dossier_id)
        requested_document = str(document_name).strip() if document_name is not None else None
        if self._document_store is None:
            return {
                "count": 0,
                "matches": [],
            }

        query_tokens = self._tokenize_text(query)
        if not query_tokens:
            query_tokens = [query.strip().lower()]

        matches: list[dict[str, Any]] = []
        for current_dossier_id, document_path in self._document_store.list_document_paths(requested_scope):
            if requested_document is not None and document_path.name != requested_document:
                continue

            text = self._load_document_text(current_dossier_id, document_path)
            if not text:
                continue

            normalized_text = text.lower()
            matched_tokens = sorted({token for token in query_tokens if token in normalized_text})
            if not matched_tokens:
                continue

            score = sum(normalized_text.count(token) for token in matched_tokens)
            matches.append(
                {
                    "dossier_id": current_dossier_id,
                    "document": document_path.name,
                    "score": int(score),
                    "matched_tokens": matched_tokens,
                    "snippet": self._build_document_snippet(text, matched_tokens),
                }
            )

        matches.sort(key=lambda item: (-int(item["score"]), str(item["dossier_id"]), str(item["document"])))
        limited_matches = matches[:limit]

        return {
            "count": len(limited_matches),
            "matches": limited_matches,
            "truncated": len(matches) > len(limited_matches),
        }

    def _entity_dossier_ids(self, entity: str) -> list[str]:
        metadata = self._graph.entity_metadata or {}
        values = metadata.get(entity) or set()
        return sorted({str(value) for value in values if str(value).strip()})

    def _entity_matches_scope(self, entity: str, scope: str | None) -> bool:
        if scope is None:
            return True
        return scope in self._entity_dossier_ids(entity)

    def _relation_matches_scope(self, subject: str, obj: str, scope: str | None) -> bool:
        if scope is None:
            return True
        return self._entity_matches_scope(subject, scope) or self._entity_matches_scope(obj, scope)

    def _build_graph_for_scope(self, scope: str | None) -> nx.DiGraph:
        if scope is None:
            return KGGen.to_nx(self._graph)

        graph_nx = nx.DiGraph()
        for entity in sorted(self._graph.entities, key=str.lower):
            if self._entity_matches_scope(entity, scope):
                graph_nx.add_node(entity)

        for subject, predicate, obj in self._graph.relations:
            if not self._relation_matches_scope(subject, obj, scope):
                continue
            graph_nx.add_node(subject)
            graph_nx.add_node(obj)
            graph_nx.add_edge(subject, obj, relation=predicate)

        return graph_nx

    def _ensure_scope_graph(self, scope: str | None) -> tuple[nx.DiGraph, float]:
        key = scope or "__all__"
        cached = self._graph_cache.get(key)
        if cached is not None:
            return cached, 0.0

        start = perf_counter()
        generated = self._build_graph_for_scope(scope)
        latency_ms = (perf_counter() - start) * 1000
        self._graph_cache[key] = generated
        return generated, float(latency_ms)

    def _exact_entity_lookup(
        self,
        *,
        exact_name: str,
        dossier_id: str | None,
    ) -> dict[str, Any]:
        scope, scope_error = self._resolve_scope(dossier_id)
        if scope_error:
            return {"error": scope_error}

        graph_nx, _ = self._ensure_scope_graph(scope)
        needle = exact_name.strip().lower()
        matches: list[str] = []
        for entity in sorted(self._graph.entities, key=str.lower):
            if entity.lower() != needle:
                continue
            if not self._entity_matches_scope(entity, scope):
                continue
            matches.append(entity)

        entities_payload = []
        for entity in matches:
            neighbors = set(graph_nx.successors(entity)) | set(graph_nx.predecessors(entity))
            entities_payload.append(
                {
                    "entity": entity,
                    "degree": int(graph_nx.degree(entity)) if entity in graph_nx else 0,
                    "dossier_ids": self._entity_dossier_ids(entity),
                    "neighbors": sorted(neighbors, key=str.lower)[:5],
                }
            )

        return {
            "requested_name": exact_name,
            "count": len(entities_payload),
            "entities": entities_payload,
            "error": (
                "no exact entity matched; use evidence_subgraph or semantic_retrieve to discover candidate entities first"
                if not entities_payload
                else None
            ),
        }

    def _evidence_subgraph(
        self,
        *,
        query: str,
        dossier_id: str | None,
        k: int,
        per_entity_edge_limit: int,
        include_documents: bool,
    ) -> dict[str, Any]:
        scope, scope_error = self._resolve_scope(dossier_id)
        if scope_error:
            return {"error": scope_error}

        semantic_result = self._semantic_retrieve(query=query, k=k, dossier_id=scope)
        candidate_entities = semantic_result.get("retrieved_nodes", [])
        anchor_entities = []
        exact_entity_candidates: list[str] = []

        for candidate in candidate_entities[:k]:
            entity = str(candidate.get("entity", "")).strip()
            if not entity:
                continue

            incident_edges = self._node_incident_edges(
                entity=entity,
                direction="both",
                limit=per_entity_edge_limit,
                dossier_id=scope,
            )
            anchor_entities.append(
                {
                    "entity": entity,
                    "score": float(candidate.get("score", 0.0) or 0.0),
                    "dossier_ids": self._entity_dossier_ids(entity),
                    "edge_count": int(incident_edges.get("count", 0) or 0),
                    "edges": list(incident_edges.get("edges", [])),
                }
            )
            exact_entity_candidates.append(entity)

        document_matches = []
        if include_documents:
            document_matches = self._document_evidence_search(
                query=query,
                dossier_id=scope,
                document_name=None,
                limit=min(k, MAX_TOOL_ITEMS),
            ).get("matches", [])

        return {
            "query": query,
            "dossier_id": scope,
            "candidate_entities": candidate_entities,
            "anchor_entities": anchor_entities,
            "exact_entity_candidates": exact_entity_candidates,
            "context": list(semantic_result.get("context", [])),
            "context_text": semantic_result.get("context_text", ""),
            "document_matches": document_matches,
            "guidance": (
                "Use exact_entity_lookup only with one of exact_entity_candidates or an exact surface form from the question."
            ),
        }

    def _entity_list(self, *, limit: int, offset: int, dossier_id: str | None) -> dict[str, Any]:
        scope, scope_error = self._resolve_scope(dossier_id)
        if scope_error:
            return {"error": scope_error}

        scoped_entities = [
            entity
            for entity in sorted(self._graph.entities, key=str.lower)
            if self._entity_matches_scope(entity, scope)
        ]
        total_count = len(scoped_entities)
        items = scoped_entities[offset:offset + limit]

        return {
            "total_count": total_count,
            "count": len(items),
            "offset": offset,
            "limit": limit,
            "truncated": (offset + len(items)) < total_count,
            "entities": items,
        }

    def _relation_filter(
        self,
        *,
        predicate: str | None,
        entity: str | None,
        limit: int,
        dossier_id: str | None,
    ) -> dict[str, Any]:
        scope, scope_error = self._resolve_scope(dossier_id)
        if scope_error:
            return {"error": scope_error}

        predicate_filter = (predicate or "").strip().lower()
        entity_filter = (entity or "").strip().lower()

        relations_payload = []
        for subject, rel_predicate, obj in sorted(
            self._graph.relations,
            key=lambda item: (item[1].lower(), item[0].lower(), item[2].lower()),
        ):
            if not self._relation_matches_scope(subject, obj, scope):
                continue
            if predicate_filter and predicate_filter not in rel_predicate.lower():
                continue
            if entity_filter and entity_filter not in subject.lower() and entity_filter not in obj.lower():
                continue
            relations_payload.append(
                {
                    "subject": subject,
                    "predicate": rel_predicate,
                    "object": obj,
                }
            )
            if len(relations_payload) >= limit:
                break

        return {
            "count": len(relations_payload),
            "relations": relations_payload,
        }

    def _relation_list(self, *, limit: int, offset: int, dossier_id: str | None) -> dict[str, Any]:
        scope, scope_error = self._resolve_scope(dossier_id)
        if scope_error:
            return {"error": scope_error}

        scoped_relations = [
            {
                "subject": subject,
                "predicate": rel_predicate,
                "object": obj,
            }
            for subject, rel_predicate, obj in sorted(
                self._graph.relations,
                key=lambda item: (item[1].lower(), item[0].lower(), item[2].lower()),
            )
            if self._relation_matches_scope(subject, obj, scope)
        ]

        total_count = len(scoped_relations)
        items = scoped_relations[offset:offset + limit]

        return {
            "total_count": total_count,
            "count": len(items),
            "offset": offset,
            "limit": limit,
            "truncated": (offset + len(items)) < total_count,
            "relations": items,
        }

    def _resolve_entity_in_scope(self, entity: str, scope: str | None) -> str | None:
        graph_nx, _ = self._ensure_scope_graph(scope)
        target = entity.strip().lower()

        for node in graph_nx.nodes:
            if node.lower() == target:
                return node

        return None

    @staticmethod
    def _incident_directions(
        *,
        direction: Literal["in", "out", "both"],
        target: str,
        subject: str,
        obj: str,
    ) -> tuple[Literal["in", "out"], ...]:
        directions: list[Literal["in", "out"]] = []
        if direction in ("out", "both") and subject == target:
            directions.append("out")
        if direction in ("in", "both") and obj == target:
            directions.append("in")
        return tuple(directions)

    def _build_incident_edge_payload(
        self,
        *,
        edge_direction: Literal["in", "out"],
        subject: str,
        rel_predicate: str,
        obj: str,
    ) -> dict[str, Any]:
        counterpart = obj if edge_direction == "out" else subject
        return {
            "direction": edge_direction,
            "subject": subject,
            "predicate": rel_predicate,
            "object": obj,
            "counterpart": counterpart,
            "counterpart_dossier_ids": self._entity_dossier_ids(counterpart),
        }

    def _node_incident_edges(
        self,
        *,
        entity: str,
        direction: Literal["in", "out", "both"],
        limit: int,
        dossier_id: str | None,
    ) -> dict[str, Any]:
        scope, scope_error = self._resolve_scope(dossier_id)
        if scope_error:
            return {"error": scope_error}

        target = self._resolve_entity_in_scope(entity, scope)
        if target is None:
            return {
                "entity": None,
                "count": 0,
                "edges": [],
                "error": "entity not found in scope; use evidence_subgraph, semantic_retrieve, or exact_entity_lookup to get an exact entity name first",
            }

        edges_payload: list[dict[str, Any]] = []
        truncated = False
        seen: set[tuple[str, str, str, str]] = set()

        for subject, rel_predicate, obj in sorted(
            self._graph.relations,
            key=lambda item: (item[1].lower(), item[0].lower(), item[2].lower()),
        ):
            if not self._relation_matches_scope(subject, obj, scope):
                continue

            for edge_direction in self._incident_directions(
                direction=direction,
                target=target,
                subject=subject,
                obj=obj,
            ):
                key = (edge_direction, subject, rel_predicate, obj)
                if key in seen:
                    continue
                seen.add(key)
                edges_payload.append(
                    self._build_incident_edge_payload(
                        edge_direction=edge_direction,
                        subject=subject,
                        rel_predicate=rel_predicate,
                        obj=obj,
                    )
                )
                if len(edges_payload) >= limit:
                    truncated = True
                    break
            if truncated:
                break

        return {
            "entity": target,
            "entity_dossier_ids": self._entity_dossier_ids(target),
            "count": len(edges_payload),
            "edges": edges_payload,
            "truncated": truncated,
        }

    def _neighbor_traversal(
        self,
        *,
        entity: str,
        depth: int,
        limit: int,
        dossier_id: str | None,
    ) -> dict[str, Any]:
        scope, scope_error = self._resolve_scope(dossier_id)
        if scope_error:
            return {"error": scope_error}

        graph_nx, _ = self._ensure_scope_graph(scope)
        seed = self._resolve_entity_in_scope(entity, scope)
        if seed is None:
            return {
                "count": 0,
                "seed_entity": None,
                "statements": [],
                "error": "entity not found in scope; use evidence_subgraph, semantic_retrieve, or exact_entity_lookup to get an exact entity name first",
            }

        statements = KGGen.retrieve_context(
            node=seed,
            graph=graph_nx,
            depth=depth,
        )
        statements = sorted(set(statements), key=str.lower)[:limit]

        return {
            "count": len(statements),
            "seed_entity": seed,
            "depth": depth,
            "statements": statements,
            "truncated": len(statements) >= limit,
        }

    def _semantic_retrieve(self, *, query: str, k: int, dossier_id: str | None) -> dict[str, Any]:
        scope, scope_error = self._resolve_scope(dossier_id)
        if scope_error:
            return {"error": scope_error}

        graph_nx, _ = self._ensure_scope_graph(scope)
        if graph_nx.number_of_nodes() == 0:
            return {
                "retrieved_nodes": [],
                "context": [],
                "context_text": "",
            }

        key = scope or "__all__"
        node_embeddings = self._embedding_cache.get(key)
        if node_embeddings is None:
            embedding_start = perf_counter()
            node_embeddings, _ = self._kg.generate_embeddings(graph_nx)
            self.embedding_latency_ms += (perf_counter() - embedding_start) * 1000
            self._embedding_cache[key] = node_embeddings

        retrieval_start = perf_counter()
        top_nodes, context, context_text = self._kg.retrieve(
            query=query,
            node_embeddings=node_embeddings,
            graph=graph_nx,
            k=k,
        )
        self.retrieval_latency_ms += (perf_counter() - retrieval_start) * 1000

        self.retrieved_nodes += len(top_nodes)
        self.context_statements += len(context)

        context_statements = sorted(context)[:MAX_CONTEXT_STATEMENTS]
        top_nodes_payload = [
            {"entity": node, "score": float(score)}
            for node, score in top_nodes[:MAX_TOOL_ITEMS]
        ]

        return {
            "retrieved_nodes": top_nodes_payload,
            "context": context_statements,
            "context_text": context_text,
        }
