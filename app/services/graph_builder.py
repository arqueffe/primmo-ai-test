from kg_gen import KGGen, Graph
from app.services.ocr_extractor import ParsedDocument

class GraphBuilder:
    
    @staticmethod
    async def build_graph(doc: ParsedDocument, kg: KGGen) -> Graph:
        graph = kg.generate(
            input_data=doc.text,
            context=f"Notarial document related to property transactions in France. File name: {doc.file_name}, Dossier ID: {doc.dossier_id}, Average Confidence: {doc.avg_confidence}, Page Count: {doc.page_count}",
        )
        return graph
    
    @staticmethod
    async def aggregate_graphs(graphs: list[Graph], kg: KGGen) -> Graph:
        return kg.aggregate(graphs)