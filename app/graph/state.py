from typing import TypedDict


class DNIState(TypedDict, total=False):
    pregunta: str

    intencion: str
    intencion_anterior: str
    tramite_actual: str
    historial: list[dict]

    pregunta_busqueda: str
    fragmentos: list[dict]
    contexto: str
    fuentes: list[dict]

    respuesta_borrador: str
    respuesta_final: str
    verificacion: str
    