"""Lectura exacta del docstore indexado; no embeddings, ranking ni TXT de respaldo."""
import re
from pathlib import Path

from langchain_core.embeddings import Embeddings
from langchain_community.vectorstores import FAISS

from app.graph.adult_context import ADULT_FILES, plan
from app.graph.context_policy import ruta_documental
from app.rag.index_builder import VECTOR_STORE_PATH

_BLOCK = re.compile(r'\[\[REGLA:([a-z_]+)\]\]\s*(.*?)\s*\[\[FIN\]\]', re.S)


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
    approved = {}
    for file in {pair[0] for pair in requested}:
        try:
            text = (Path(__file__).resolve().parents[2] / 'data' / 'raw' / file).read_text(encoding='utf-8')
        except OSError:
            continue
        for match in _BLOCK.finditer(text):
            approved[file, match[1]] = match[0].strip()
    try:
        index = cargar_indice_exacto(ruta_indice)
    except (OSError, ValueError, RuntimeError, EOFError):
        return []
    found, conflicts = {}, set()
    for doc_id in dict.fromkeys(index.index_to_docstore_id.values()):
        doc = index.docstore.search(doc_id)
        if not hasattr(doc, 'metadata') or not hasattr(doc, 'page_content'):
            continue
        file, chunk = doc.metadata.get('archivo'), doc.metadata.get('chunk')
        if file not in {key[0] for key in requested} or type(chunk) is not int or chunk < 0:
            continue
        match = _BLOCK.fullmatch(doc.page_content.strip())
        if not match or not match[2].strip() or len(doc.page_content) > 1800:
            continue
        key = file, match[1]
        if key not in requested or doc.metadata.get('regla', match[1]) != match[1]:
            continue
        if approved.get(key) != doc.page_content.strip():
            continue  # Regla indexada distinta del corpus actual: no rescatar desde TXT.
        if key in found and found[key]['contenido'].strip() != doc.page_content.strip():
            conflicts.add(key)
        else:
            found[key] = {'contenido': doc.page_content, 'score': None,
                          'metadata': {**doc.metadata, 'recuperacion': 'exacta'}}
    return [found[key] for key in sorted(found.keys() - conflicts)]
