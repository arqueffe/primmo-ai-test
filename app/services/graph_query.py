from kg_gen import KGGen, Graph
from openai import OpenAI

from app.services.graph_store import GraphStore

class GraphQuery:
    
    @staticmethod
    async def query_graph(query: str, graph_store: GraphStore, kg: KGGen, api_key: str) -> str | None:
        graph = graph_store.graph
        if graph is None:
            return None
        graph_nx = KGGen.to_nx(graph)
        node_embeddings, relation_embeddings = kg.generate_embeddings(graph_nx)
        top_nodes, context, context_text = kg.retrieve(
            query=query,
            node_embeddings=node_embeddings,
            graph=graph_nx,
        )
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": f"Answer the following question based on the context: {context_text}"},
                {"role": "user", "content": f"Question: {query}"}
            ]
        )
        return response.choices[0].message.content