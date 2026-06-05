import json
import os
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import time
from typing import List
from kg_gen import Graph, KGGen
from dotenv import load_dotenv

load_dotenv()

VISUALIZE_KNOWLEDGE_GRAPH = False
GET_LATEST_KNOWLEDGE_GRAPH = True
CLUSTER_KNOWLEDGE_GRAPH = True
VISUALIZE_CLUSTERED_KNOWLEDGE_GRAPH = False
GET_LATEST_CLUSTERED_KNOWLEDGE_GRAPH = True

api_key = os.getenv("API_KEY")

MODEL = "openai/gpt-4o"
RETRIEVAL_MODEL = "maastrichtlawtech/dpr-legal-french"
QUERY = "Qui sont les acheteurs et les vendeurs sur le dossier?"

kg = KGGen(
    model=MODEL,
    temperature=0.0,
    api_key=api_key if api_key else "",
    retrieval_model=RETRIEVAL_MODEL,
)


@dataclass
class ParsedDocument:
    text: str
    file_name: str
    folder_id: str
    avg_confidence: float
    page_count: int


def extract_text(json_path: Path) -> ParsedDocument:
    with open(json_path, "r") as f:
        data = json.load(f)

    text = data.get("responses", [{}])[0].get("fullTextAnnotation", {}).get("text", "")
    file_name = json_path.stem
    folder_id = json_path.parent.stem
    page_count = len(
        data.get("responses", [{}])[0].get("fullTextAnnotation", {}).get("pages", 0)
    )
    avg_confidence = sum(
        page.get("confidence", 0.0)
        for page in data.get("responses", [{}])[0]
        .get("fullTextAnnotation", {})
        .get("pages", [])
    ) / max(page_count, 1)

    return ParsedDocument(
        text=text,
        file_name=file_name,
        folder_id=folder_id,
        avg_confidence=avg_confidence,
        page_count=page_count,
    )


def recover_documents(folder_path: Path) -> list[ParsedDocument]:
    documents = []
    for json_file in folder_path.glob("*.json"):
        try:
            document = extract_text(json_file)
            documents.append(document)
        except Exception as e:
            print(f"Error processing {json_file}: {e}")
    return documents


def build_individual_kg(documents: list[ParsedDocument]) -> List[Graph]:
    graphs = []
    for doc in documents:
        graph = kg.generate(
            input_data=doc.text,
            context=f"Notarial document related to property transactions in France. File name: {doc.file_name}, Folder ID: {doc.folder_id}, Average Confidence: {doc.avg_confidence}, Page Count: {doc.page_count}",
        )
        graphs.append(graph)
    return graphs


def aggregate_graphs(graphs: list[Graph]) -> Graph:
    return kg.aggregate(graphs)


def build_knowledge_graph_by_concatenation(folder_path: Path) -> Graph:
    documents = recover_documents(folder_path)
    combined_text = "\n".join(doc.text for doc in documents)
    context = "Notarial documents related to property transactions in France. " + ", ".join(
        f"{doc.file_name} (Folder ID: {doc.folder_id}, Avg Confidence: {doc.avg_confidence}, Page Count: {doc.page_count})"
        for doc in documents
    )
    graph = kg.generate(input_data=combined_text, context=context)
    return graph


def build_knowledge_graph_by_aggregation(folder_path: Path) -> Graph:
    documents = recover_documents(folder_path)
    individual_graphs = build_individual_kg(documents)
    aggregated_graph = aggregate_graphs(individual_graphs)
    return aggregated_graph


def get_latest_knowledge_graph(output_dir: Path) -> Graph:
    latest_knowledge_graph_path = max(
        output_dir.glob("knowledge_graph_*.json"), key=os.path.getctime
    )
    knowledge_graph = KGGen.from_file(latest_knowledge_graph_path.as_posix())
    return knowledge_graph


def get_latest_clustered_knowledge_graph(output_dir: Path) -> Graph:
    latest_clustered_knowledge_graph_path = max(
        output_dir.glob("clustered_knowledge_graph_*.json"), key=os.path.getctime
    )
    clustered_knowledge_graph = KGGen.from_file(
        latest_clustered_knowledge_graph_path.as_posix()
    )
    return clustered_knowledge_graph


if __name__ == "__main__":
    folder_path = Path("documents/dossier_1")
    time = time.strftime("%Y%m%d_%H%M%S")
    output_dir = Path(f"outputs")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_kg_dir = output_dir / f"{time}"
    output_kg_dir.mkdir(parents=True, exist_ok=True)

    if GET_LATEST_KNOWLEDGE_GRAPH:
        knowledge_graph = get_latest_knowledge_graph(output_dir)
    else:
        knowledge_graph = build_knowledge_graph_by_aggregation(folder_path)

    knowledge_graph.to_file(output_kg_dir.as_posix() + "/knowledge_graph.json")
    if VISUALIZE_KNOWLEDGE_GRAPH:
        kg.visualize(
            knowledge_graph,
            output_kg_dir.as_posix() + "/output.html",
            open_in_browser=True,
        )

    clustered_graph = None

    if CLUSTER_KNOWLEDGE_GRAPH:
        if GET_LATEST_CLUSTERED_KNOWLEDGE_GRAPH:
            clustered_graph = get_latest_clustered_knowledge_graph(output_dir)
        else:
            clustered_graph = kg.deduplicate(
                knowledge_graph,
                model=MODEL,
                temperature=0.0,
                api_key=api_key if api_key else "",
                context="Main entities in notarial documents related to property transactions in France",
            )
        KGGen.export_graph(
            clustered_graph,
            str(output_kg_dir / "clustered_knowledge_graph.json"),
        )
        if VISUALIZE_CLUSTERED_KNOWLEDGE_GRAPH:
            kg.visualize(
                clustered_graph,
                output_kg_dir.as_posix() + "/output_clustered.html",
                open_in_browser=True,
            )
            
    print("Knowledge graph generation and clustering completed. Starting retrieval and question answering...")

    graph_to_embed = clustered_graph if clustered_graph else knowledge_graph
    graph_nx = KGGen.to_nx(graph_to_embed)
    node_embeddings, relation_embeddings = kg.generate_embeddings(graph=graph_nx)
    top_nodes, context, context_text = kg.retrieve(
        query=QUERY,
        node_embeddings=node_embeddings,
        graph=graph_nx
    )
    
    print("Nodes, relations, and context retrieved for the query.")
    
    # Add a simple query answering mechanism using the retrieved context using OPENAI API
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"Answer the following question based on the context: {context_text}"},
            {"role": "user", "content": f"Question: {QUERY}"}
        ]
    )
    print("Answer:", response.choices[0].message.content)
