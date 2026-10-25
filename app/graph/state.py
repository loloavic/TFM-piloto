from dataclasses import dataclass
from typing import Literal, NotRequired, TypedDict


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


class DatoContextual(TypedDict):
    valor: str
    estado: Literal['desconocido', 'confirmado', 'conflicto']
    turno: int
    revision: int
    origen: Literal['ausente', 'explicito', 'observacion']


class ContextoCanonico(TypedDict):
    turno: int
    revision: int
    ambito: Literal['desconocido', 'dni', 'fuera_alcance']
    titular: DatoContextual
    edad: DatoContextual
    operacion: DatoContextual
    rechazadas: list[str]
    pendientes: dict[str, str]  # motivo -> faltante/contradiccion
    propuesta_operacion: str
    tema: str
    consulta_pendiente: str
    retomar: str
    ultima_ruta: str  # Solo presentación histórica, nunca fuente de hechos.
    # Extensiones optativas V2; ausentes en el recorrido V1.
    dni_previo: NotRequired[DatoContextual]
    funcion_documento: NotRequired[DatoContextual]
    relacion: NotRequired[DatoContextual]  # Informativa, no selecciona persona ni edad.


@dataclass(frozen=True)
class EvidenciaTurno:
    """Solo categorías del mensaje actual; no texto ni datos personales nuevos."""
    titular: str = ''
    edad: str = ''
    operacion: str = ''
    rechazadas: tuple[str, ...] = ()
    dudas: tuple[str, ...] = ()
    tema: str = 'otra'
    pregunta_tema: bool = False
    dni: bool = False
    otro_tramite: bool = False
    otro_solo: bool = False
    otro_necesitado: bool = False
    mencion_otro: bool = False
    apoyo: bool = False
    finalidad_dni: bool = False
    mixto: bool = False
    funcion_documento: str = ''
    cambio: bool = False
    rectificacion: bool = False
    otro_titular: bool = False
    solicitud: bool = False
    observacion: bool = False
    abandonar: bool = False


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
    contexto_canonico: ContextoCanonico
    historial: list[dict]

    pregunta_busqueda: str
    fragmentos: list[dict]
    contexto: str
    fuentes: list[dict]

    respuesta_borrador: str
    respuesta_final: str
    verificacion: str
