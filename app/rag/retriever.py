from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

from app.core.config import settings
from app.rag.index_builder import VECTOR_STORE_PATH


def cargar_vector_store(ruta_indice: str = VECTOR_STORE_PATH) -> FAISS:
    embeddings = OpenAIEmbeddings(
        model=settings.openai_embedding_model,
        api_key=settings.openai_api_key.get_secret_value(),
        request_timeout=settings.provider_timeout_seconds, max_retries=0,
    )

    return FAISS.load_local(
        ruta_indice,
        embeddings,
        allow_dangerous_deserialization=True,
    )


def recuperar_contexto(
    pregunta: str,
    k: int = 3,
) -> list[dict]:
    vector_store = cargar_vector_store()
    resultados = vector_store.similarity_search_with_score(pregunta, k=k)

    contexto = []

    for documento, score in resultados:
        contexto.append(
            {
                "contenido": documento.page_content,
                "score": float(score),
                "metadata": documento.metadata,
            }
        )

    return contexto