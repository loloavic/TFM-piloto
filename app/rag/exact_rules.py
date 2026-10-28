"""Lectura exacta del docstore indexado; no embeddings, ranking ni TXT de respaldo."""
from pathlib import Path

from langchain_core.embeddings import Embeddings
from langchain_community.vectorstores import FAISS

from app.graph.adult_context import ADULT_FILES, plan
from app.graph.context_policy import ruta_documental
from app.rag.index_builder import VECTOR_STORE_PATH
from app.rag.rule_integrity import RuleIntegrity, IntegrityResults


class _SinEmbeddings(Embeddings):
    def embed_documents(self, texts):
        raise RuntimeError('La lectura exacta no genera embeddings')

    def embed_query(self, text):
        raise RuntimeError('La lectura exacta no consulta embeddings')


def cargar_indice_exacto(ruta_indice=VECTOR_STORE_PATH):
    # Mismo índice local confiable que ya utiliza el recuperador semántico.
    return FAISS.load_local(str(Path(ruta_indice)), _SinEmbeddings(), allow_dangerous_deserialization=True)


def recuperar_reglas_exactas(contexto, faltantes, ruta_indice=VECTOR_STORE_PATH):
    """Solo pares autorizados, completos y sin versiones contradictorias.

    La metadata existente archivo/chunk basta: no exige reconstruir el índice.
    No se leen documentos del corpus para suplir reglas ausentes del docstore.
    """
    if ruta_documental(contexto) not in ADULT_FILES:
        return []
    authorized = {(file, rule) for file, rules in plan(contexto).items() for rule in rules}
    requested = set(faltantes)
    if not requested or not requested <= authorized:
        return []
    validator = RuleIntegrity(requested)
    try:
        index = cargar_indice_exacto(ruta_indice)
    except (OSError, ValueError, RuntimeError, EOFError):
        return []
    candidates = []
    for doc_id in dict.fromkeys(index.index_to_docstore_id.values()):
        doc = index.docstore.search(doc_id)
        if hasattr(doc, 'metadata') and hasattr(doc, 'page_content'):
            candidates.append({'contenido': doc.page_content, 'score': None,
                               'metadata': {**doc.metadata, 'recuperacion': 'exacta'}})
    validator.add(candidates)
    return IntegrityResults(validator)
