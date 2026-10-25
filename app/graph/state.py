from typing import Literal, TypedDict


class ContextoSolicitante(TypedDict, total=False):
    grupo_edad: Literal["menor", "adulto", "desconocido"]
    destinatario: Literal["descendiente", "menor", "adulto", "propio", "desconocido"]


class DecisionClasificacion(TypedDict):
    # Códigos semánticos; no copiar la pregunta ni almacenar nuevas identidades.
    tramite_candidato: str
    evidencias: list[str]
    faltantes: list[str]
    contradicciones: list[str]
    consulta_pendiente: str  # Tema del pedido original, recuperable sin texto personal.


class DNIState(TypedDict, total=False):
    pregunta: str

    intencion: str
    intencion_anterior: str
    # Identificación del trámite (puede no estar documentado), no tema del turno.
    tramite_actual: str
    operacion_dni: str
    tipo_consulta: Literal["requisitos", "coste", "plazo", "cita", "seguimiento", "otra"]
    contexto_solicitante: ContextoSolicitante  # Solo grupo de edad y destinatario genérico.
    tramite_documentado: bool
    estado_documental: str
    requiere_aclaracion: bool
    motivo_aclaracion: str
    decision: DecisionClasificacion
    historial: list[dict]

    pregunta_busqueda: str
    fragmentos: list[dict]
    contexto: str
    fuentes: list[dict]

    respuesta_borrador: str
    respuesta_final: str
    verificacion: str
