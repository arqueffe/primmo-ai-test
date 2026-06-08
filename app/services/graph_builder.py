from kg_gen import KGGen, Graph
from app.services.ocr_extractor import ParsedDocument

class GraphBuilder:
    
    @staticmethod
    async def build_graph(doc: ParsedDocument, kg: KGGen) -> Graph:
        graph = kg.generate(
            input_data=doc.text,
            context=f"Notarial document related to property transactions in France. File name: {doc.file_name}, Dossier ID: {doc.dossier_id}, Average Confidence: {doc.avg_confidence}, Page Count: {doc.page_count}",
        )

        # Ensure relation endpoints are represented as entities.
        relation_entities = set()
        for subject, _, obj in graph.relations:
            relation_entities.add(subject)
            relation_entities.add(obj)
        graph.entities.update(relation_entities)

        # Persist dossier scope on each extracted entity for downstream filtering.
        entity_metadata = graph.entity_metadata or {}
        for entity in graph.entities:
            if entity not in entity_metadata:
                entity_metadata[entity] = set()
            entity_metadata[entity].add(doc.dossier_id)
        graph.entity_metadata = entity_metadata
        return graph
    
    @staticmethod
    async def aggregate_graphs(graphs: list[Graph], kg: KGGen) -> Graph:
        return kg.aggregate(graphs)