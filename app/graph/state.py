from dataclasses import dataclass
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
    consulta_renovacion: list[str]  # Propósito categórico; nunca texto del historial.
    consulta_pendiente: str
    retomar: str
    condiciones_adulto: dict[str, DatoContextual]
    ultima_ruta: str  # Solo presentación histórica, nunca fuente de hechos.


@dataclass(frozen=True)
class EvidenciaTurno:
    """Solo categorías del mensaje actual; no texto ni datos personales nuevos."""
    objetivo_independiente: bool = False
    consulta_renovacion: tuple[str, ...] = ()
    respuesta_apellido: str = ''
    respuesta_nacionalidad: str = ''
    lugar_confirmado: str = ''
    respuesta_binaria: str = ''
    condiciones_adulto: tuple[tuple[str, str], ...] = ()
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
    referencia_azul: bool = False
    tiene_amarillo: bool = False
    nunca_tuvo_dni: bool = False


class DNIState(TypedDict, total=False):
    pregunta: str
    respuesta_social: str  # Respuesta efímera; vacía en cada turno material.

    intencion: str
    intencion_anterior: str
    # Identificación del trámite (puede no estar documentado), no tema del turno.
    tramite_actual: str
    operacion_dni: str
    tipo_consulta: Literal["requisitos", "advertencias", "fotografias", "coste", "plazo", "cita", "seguimiento", "otra"]
    contexto_solicitante: ContextoSolicitante  # Solo grupo de edad y destinatario genérico.
    tramite_documentado: bool
    estado_documental: str
    requiere_aclaracion: bool
    motivo_aclaracion: str
    decision: DecisionClasificacion
    contexto_canonico: ContextoCanonico
    historial: list[dict]

    pregunta_busqueda: str
    reglas_faltantes: list[str]
    rechazos_documentales: list[str]
    fragmentos: list[dict]
    contexto: str
    fuentes: list[dict]

    respuesta_borrador: str
    respuesta_final: str
    verificacion: str
