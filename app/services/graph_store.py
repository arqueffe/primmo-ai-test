from kg_gen import KGGen, Graph

class GraphStore:
    def __init__(self):
        self._graph : Graph | None = None
        
    @property
    def graph(self) -> Graph | None:
        return self._graph
    
    def update_graph(self, new_graph: Graph):
        self._graph = new_graph
        
    def to_dict(self) -> dict:
        if self._graph is None:
            return {}
        return KGGen.to_dict(self._graph)
    
    def to_json(self) -> str:
        if self._graph is None:
            return "{}"
        return KGGen.to_json(self._graph)