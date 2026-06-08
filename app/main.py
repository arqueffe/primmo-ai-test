import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from kg_gen.kg_gen import KGGen

from app.api.router import api_router
from app.services.graph_store import GraphStore
from app.core.config import settings

MODEL = "openai/gpt-4o"
RETRIEVAL_MODEL = "maastrichtlawtech/dpr-legal-french"

def create_app() -> FastAPI:
    api_key = os.getenv("API_KEY")
    graph_store = GraphStore()
    kg = KGGen(
        model=MODEL,
        temperature=0.0,
        api_key=api_key if api_key else "",
        retrieval_model=RETRIEVAL_MODEL,
    )
    
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.api_prefix)
    
    app.state.graph_store = graph_store
    app.state.kg = kg
    app.state.api_key = api_key
    
    return app


app = create_app()
