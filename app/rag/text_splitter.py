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