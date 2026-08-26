from pathlib import Path


def cargar_documentos_txt(ruta_directorio: str = "data/raw") -> list[dict]:
    directorio = Path(ruta_directorio)

    if not directorio.exists():
        raise FileNotFoundError(f"No existe el directorio: {ruta_directorio}")

    documentos = []

    for archivo in directorio.glob("*.txt"):
        contenido = archivo.read_text(encoding="utf-8").strip()

        if not contenido:
            continue

        documentos.append(
            {
                "archivo": archivo.name,
                "ruta": str(archivo),
                "contenido": contenido,
            }
        )

    return documentos