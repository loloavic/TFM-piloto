import csv
import json
from datetime import datetime
from pathlib import Path


LOG_PATH = Path("data/logs/consultas_log.csv")


def registrar_consulta(
    pregunta: str,
    respuesta: str,
    intencion: str,
    verificacion: str,
    fuentes: list[dict],
) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    archivo_existe = LOG_PATH.exists()

    with LOG_PATH.open(mode="a", newline="", encoding="utf-8") as archivo:
        columnas = [
            "fecha_hora",
            "pregunta",
            "intencion",
            "verificacion",
            "respuesta",
            "fuentes",
        ]

        writer = csv.DictWriter(archivo, fieldnames=columnas)

        if not archivo_existe:
            writer.writeheader()

        writer.writerow(
            {
                "fecha_hora": datetime.now().isoformat(timespec="seconds"),
                "pregunta": pregunta,
                "intencion": intencion,
                "verificacion": verificacion,
                "respuesta": respuesta,
                "fuentes": json.dumps(fuentes, ensure_ascii=False),
            }
        )