import json
from pathlib import Path

from kg_gen import KGGen, Graph

class GraphStore:
    def __init__(self, state_file: str | Path | None = None):
        self._global_graph: Graph | None = None
        self._dossier_graphs: dict[str, Graph] = {}
        self._state_file = Path(state_file) if state_file else None
        
    @property
    def graph(self) -> Graph | None:
        return self._global_graph

    @property
    def dossier_ids(self) -> list[str]:
        return sorted(self._dossier_graphs.keys())

    def get_graph(self, dossier_id: str | None = None) -> Graph | None:
        if dossier_id is None:
            return self._global_graph
        return self._dossier_graphs.get(dossier_id)
    
    def update_graph(self, new_graph: Graph):
        self._normalize_graph(new_graph)
        self._global_graph = new_graph
        self.save_state()

    def update_dossier_graph(self, dossier_id: str, document_graph: Graph, kg: KGGen) -> None:
        self._normalize_graph(document_graph, fallback_dossier_id=dossier_id)
        current_dossier_graph = self._dossier_graphs.get(dossier_id)
        if current_dossier_graph is None:
            self._dossier_graphs[dossier_id] = document_graph
        else:
            aggregated = kg.aggregate(
                [current_dossier_graph, document_graph]
            )
            self._normalize_graph(aggregated, fallback_dossier_id=dossier_id)
            self._dossier_graphs[dossier_id] = aggregated
        self.save_state()

    def rebuild_global_graph(self, kg: KGGen) -> None:
        graphs = list(self._dossier_graphs.values())
        if not graphs:
            self._global_graph = None
            self.save_state()
            return
        self._global_graph = kg.aggregate(graphs)
        self._normalize_graph(self._global_graph)
        self.save_state()
        
    def to_dict(self, dossier_id: str | None = None) -> dict:
        graph = self.get_graph(dossier_id)
        if graph is None:
            return {}
        graph_dict = KGGen.to_dict(graph)
        metadata = graph_dict.get("entity_metadata")
        if metadata:
            graph_dict["entity_metadata"] = {
                entity: sorted(values) if isinstance(values, set) else values
                for entity, values in metadata.items()
            }
        return graph_dict
    
    def to_json(self, dossier_id: str | None = None) -> str:
        return json.dumps(self.to_dict(dossier_id=dossier_id), indent=2)

    def load_state(self) -> bool:
        if self._state_file is None or not self._state_file.exists():
            return False

        try:
            with self._state_file.open("r", encoding="utf-8") as f:
                payload = json.load(f)

            global_graph_data = payload.get("global_graph")
            dossier_graphs_data = payload.get("dossier_graphs", {})

            self._global_graph = KGGen.from_dict(global_graph_data) if global_graph_data else None
            self._dossier_graphs = {
                dossier_id: KGGen.from_dict(graph_data)
                for dossier_id, graph_data in dossier_graphs_data.items()
                if graph_data
            }

            for dossier_id, dossier_graph in self._dossier_graphs.items():
                self._normalize_graph(dossier_graph, fallback_dossier_id=dossier_id)
            if self._global_graph is not None:
                self._normalize_graph(self._global_graph)

            return True
        except Exception:
            self._global_graph = None
            self._dossier_graphs = {}
            return False

    def save_state(self) -> None:
        if self._state_file is None:
            return

        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "global_graph": self.to_dict(),
            "dossier_graphs": {
                dossier_id: self.to_dict(dossier_id)
                for dossier_id in self.dossier_ids
            },
        }
        with self._state_file.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    @staticmethod
    def _normalize_graph(graph: Graph, fallback_dossier_id: str | None = None) -> None:
        relation_entities, relation_edges = GraphStore._collect_relation_components(graph)
        graph.entities.update(relation_entities)
        graph.edges.update(relation_edges)

        normalized_metadata = GraphStore._normalize_metadata_values(graph.entity_metadata)
        GraphStore._fill_missing_metadata(
            entities=graph.entities,
            metadata=normalized_metadata,
            fallback_dossier_id=fallback_dossier_id,
        )

        graph.entity_metadata = normalized_metadata

    @staticmethod
    def _collect_relation_components(graph: Graph) -> tuple[set[str], set[str]]:
        relation_entities: set[str] = set()
        relation_edges: set[str] = set()
        for subject, predicate, obj in graph.relations:
            relation_entities.add(subject)
            relation_entities.add(obj)
            relation_edges.add(predicate)
        return relation_entities, relation_edges

    @staticmethod
    def _normalize_metadata_values(
        metadata: dict[str, set[str]] | None,
    ) -> dict[str, set[str]]:
        if not metadata:
            return {}
        return {
            entity: set(values) if values else set()
            for entity, values in metadata.items()
        }

    @staticmethod
    def _fill_missing_metadata(
        entities: set[str],
        metadata: dict[str, set[str]],
        fallback_dossier_id: str | None,
    ) -> None:
        for entity in entities:
            values = metadata.get(entity, set())
            if not values and fallback_dossier_id:
                values = {fallback_dossier_id}
            metadata[entity] = values