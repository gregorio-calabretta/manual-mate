import os
from pathlib import Path

from dotenv import load_dotenv

from config import TOP_K


ROOT = Path(__file__).resolve().parent


def carica_configurazione() -> None:
    # Anche da un'altra cartella, la CLI e Streamlit leggono lo stesso file .env.
    load_dotenv(ROOT / ".env")


def crea_assistente(chiave: str):
    # Le tracce del client omettono il testo di input e output.
    os.environ["DATAPIZZA_TRACE_CLIENT_IO"] = "false"
    os.environ.setdefault("DATAPIZZA_AGENT_LOG_LEVEL", "WARNING")

    from datapizza.clients.openai import OpenAIClient
    from datapizza.embedders.openai import OpenAIEmbedder
    from datapizza.vectorstores.qdrant import QdrantVectorstore

    from assistente import Assistente
    from indice import IndiceManuali

    # L'agente sceglie i tool con il modello conversazionale. L'embedder produce i vettori per Qdrant.
    client = OpenAIClient(
        api_key=chiave, model=os.getenv("OPENAI_MODEL") or "gpt-4o-mini", timeout=30, max_retries=1,
    )
    embedder = OpenAIEmbedder(api_key=chiave, model_name="text-embedding-3-small")
    embedder.client = client.client
    qdrant = QdrantVectorstore(
        host=os.getenv("QDRANT_HOST") or "127.0.0.1",
        port=int(os.getenv("QDRANT_PORT") or "16333"), timeout=5,
    )
    return Assistente(IndiceManuali(embedder, qdrant, top_k=int(os.getenv("RAG_TOP_K") or TOP_K)), client)
