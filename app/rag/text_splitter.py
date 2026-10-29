import re

from langchain_text_splitters import RecursiveCharacterTextSplitter


def dividir_documentos(
    documentos: list[dict],
    chunk_size: int = 800,
    chunk_overlap: int = 120,
) -> list[dict]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ".", " ", ""],
    )

    fragmentos = []

    for documento in documentos:
        if documento['archivo'] in {
            'dni_mayor_renovacion.txt', 'dni_mayor_rectificacion.txt', 'dni_mayor_estado_civil.txt'
        }:
            # Mantener cada regla completa, sin solapamiento entre condiciones.
            partes = re.findall(r'\[\[REGLA:[a-z_]+\]\].*?\[\[FIN\]\]',
                                documento['contenido'], flags=re.S)
            if not partes or any(len(p) > 1800 for p in partes):
                raise ValueError('Formato o tamaño inválido de reglas documentales de adulto')
        else:
            partes = splitter.split_text(documento["contenido"])

        for indice, texto in enumerate(partes):
            fragmentos.append(
                {
                    "id": f'{documento["archivo"]}::chunk_{indice}',
                    "archivo": documento["archivo"],
                    "ruta": documento["ruta"],
                    "contenido": texto,
                    "chunk": indice,
                }
            )

    return fragmentos