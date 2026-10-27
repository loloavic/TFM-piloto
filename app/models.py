
from pydantic import BaseModel, Field, field_validator
from app.core.query_validation import validar_consulta


class FuenteResponse(BaseModel):
    archivo: str
    chunk: int
    distancia: float


class ConsultaRequest(BaseModel):
    pregunta: str = Field(
        min_length=2,
        max_length=1000,
        description="Consulta de 3 a 1000 caracteres o respuesta breve sí, si o no",
    )

    @field_validator("pregunta")
    @classmethod
    def validar_pregunta(cls, value: str) -> str:
        return validar_consulta(value)

    session_id: str | None = Field(
        default=None,
        description="Identificador temporal; continuar requiere X-Session-Token",
        max_length=128,
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
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