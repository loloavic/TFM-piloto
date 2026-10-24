from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from app.core.config import settings
from app.rag.document_loader import cargar_documentos_txt
from app.rag.text_splitter import dividir_documentos


VECTOR_STORE_PATH = "data/vector_store/faiss_index"


def crear_indice_faiss(
    ruta_documentos: str = "data/raw",
    ruta_indice: str = VECTOR_STORE_PATH,
) -> int:
    documentos = cargar_documentos_txt(ruta_documentos)
    fragmentos = dividir_documentos(documentos)

    if not fragmentos:
        raise ValueError("No se encontraron fragmentos para indexar.")

    embeddings = OpenAIEmbeddings(
        model=settings.openai_embedding_model,
        api_key=settings.openai_api_key.get_secret_value(),
        request_timeout=settings.provider_timeout_seconds, max_retries=0,
    )

    docs = [
        Document(
            page_content=fragmento["contenido"],
            metadata={
                "id": fragmento["id"],
                "archivo": fragmento["archivo"],
                "ruta": fragmento["ruta"],
                "chunk": fragmento["chunk"],
            },
        )
        for fragmento in fragmentos
    ]

    vector_store = FAISS.from_documents(docs, embeddings)

    Path(ruta_indice).parent.mkdir(parents=True, exist_ok=True)
    vector_store.save_local(ruta_indice)

    return len(docs)