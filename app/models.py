
from pydantic import BaseModel, Field


class FuenteResponse(BaseModel):
    archivo: str
    chunk: int
    distancia: float


class ConsultaRequest(BaseModel):
    pregunta: str = Field(
        min_length=3,
        max_length=1000,
        description="Consulta formulada por el ciudadano",
    )

    session_id: str | None = Field(
        default=None,
        description="Identificador temporal de la conversación",
    )


class ConsultaResponse(BaseModel):
    id_consulta: str
    session_id: str
    pregunta: str
    estado: str
    respuesta: str
    intencion: str
    verificacion: str
    fuentes: list[FuenteResponse] = []

class ConteoResponse(BaseModel):
    categoria: str
    cantidad: int


class EvaluacionResumenResponse(BaseModel):
    total_consultas: int
    consultas_fuera_alcance: int
    consultas_observadas: int
    resumen_intenciones: list[ConteoResponse]
    resumen_verificacion: list[ConteoResponse]

class ConsultaLogResponse(BaseModel):
    fecha_hora: str
    pregunta: str
    intencion: str
    verificacion: str
    respuesta: str
    fuentes: str


class ConsultasLogResponse(BaseModel):
    total: int
    consultas: list[ConsultaLogResponse]