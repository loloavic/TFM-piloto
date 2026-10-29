"""Métricas sin texto libre, credenciales ni identificadores de sesión."""
import csv
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

from app.graph.context_policy import DOCUMENTADOS

# No volver a abrir el CSV histórico que contenía preguntas y respuestas.
LOG_PATH = Path('data/logs/consultas_metricas.csv')
LOG_LOCK = RLock()
INTENCIONES = DOCUMENTADOS | {'fuera_alcance', 'general'}


def registrar_consulta(pregunta: str, respuesta: str, intencion: str,
                       verificacion: str, fuentes: list[dict]) -> None:
    # Argumentos conservados para compatibilidad interna; no persistir su texto.
    with LOG_LOCK:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        exists = LOG_PATH.exists()
        with LOG_PATH.open('a', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=[
                'fecha_hora', 'pregunta', 'intencion', 'verificacion', 'respuesta', 'fuentes',
            ])
            if not exists:
                writer.writeheader()
            writer.writerow({
                'fecha_hora': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                'pregunta': '', 'respuesta': '', 'fuentes': '[]',
                'intencion': intencion if intencion in INTENCIONES else 'general',
                'verificacion': ('ok' if verificacion == 'ok' else 'abstencion_documental'
                                 if verificacion == 'abstencion_documental' or verificacion.startswith('abstencion_documental:')
                                 else 'observada'),
            })
