"""V2.1: frontera inerte de interpretación; no clasifica ni autoriza documentos."""
import json
from dataclasses import dataclass
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

Dimension = Literal['ambito', 'titular', 'edad', 'operacion', 'tema',
                    'dni_previo', 'funcion_documento', 'referencia_titular']
Acto = Literal['solicitud_afirmativa', 'negacion', 'observacion', 'aclaracion']
Motivo = Literal['ambito', 'titular', 'edad', 'operacion', 'tema', 'dni_previo',
                 'documento', 'referencia', 'contradiccion']
Estado = Literal['suficiente', 'requiere_aclaracion', 'insuficiente_o_invalida']

# Vocabulario compatible con state/context_policy; duplicado es una operación
# reconocible, NO una ampliación del corpus ni una ruta autorizada.
VALORES = {
    'ambito': {'dni', 'fuera_alcance', 'desconocido'},
    'titular': {'descendiente', 'menor', 'adulto', 'propio', 'desconocido'},
    'edad': {'menor', 'adulto', 'desconocido'},
    'operacion': {'primera_vez', 'renovacion', 'duplicado', 'desconocido'},
    'tema': {'requisitos', 'coste', 'plazo', 'cita', 'seguimiento', 'otra'},
    'dni_previo': {'si', 'no', 'desconocido'},
    'funcion_documento': {'titular', 'apoyo', 'ambigua', 'desconocido'},
    'referencia_titular': {'actual', 'otro', 'varios', 'ambigua'},
}
Valor = Literal['dni', 'fuera_alcance', 'desconocido', 'descendiente', 'menor',
                'adulto', 'propio', 'primera_vez', 'renovacion', 'duplicado',
                'requisitos', 'coste', 'plazo', 'cita', 'seguimiento', 'otra',
                'si', 'no', 'titular', 'apoyo', 'ambigua', 'actual', 'otro', 'varios']


class Estricto(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', frozen=True,
                              hide_input_in_errors=True)


class EvidenciaInterpretada(Estricto):
    dimension: Dimension
    valor: Valor
    acto: Acto
    # Procedencia lingüística, no confianza ni permiso para heredar hechos.
    origen: Literal['explicito_turno', 'referencia_contextual']
    sujeto: Literal['objetivo', 'otro', 'no_resuelto']

    @model_validator(mode='after')
    def coherencia(self) -> Self:
        if self.valor not in VALORES[self.dimension]:
            raise ValueError('valor_incompatible')
        return self


class InterpretacionTurno(Estricto):
    version: Literal['2.1']
    evidencias: list[EvidenciaInterpretada] = Field(max_length=32)
    faltantes: list[Motivo] = Field(max_length=9)
    contradicciones: list[Motivo] = Field(max_length=9)

    @model_validator(mode='after')
    def sin_duplicados(self) -> Self:
        keys = [tuple(e.model_dump().values()) for e in self.evidencias]
        if (len(set(keys)) != len(keys)
                or len(set(self.faltantes)) != len(self.faltantes)
                or len(set(self.contradicciones)) != len(self.contradicciones)):
            raise ValueError('duplicados')
        return self


class EntradaInterpretacion(Estricto):
    """Metadatos internos asignados por el llamador, nunca por el proveedor.

    El texto reducido se entregará al futuro proveedor por el canal existente;
    este contrato no lo copia ni guarda contexto o historial alternativos.
    """
    turno: int = Field(ge=1)
    revision: int = Field(ge=0)


@dataclass(frozen=True)
class ResultadoInterpretacion:
    estado: Estado
    motivos: tuple[Motivo, ...]
    entrada: EntradaInterpretacion | None
    interpretacion: InterpretacionTurno | None


def _sin_claves_repetidas(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('clave_repetida')
        result[key] = value
    return result


def validar_interpretacion(entrada: object, salida: object) -> ResultadoInterpretacion:
    """Valida dict/JSON sin propagar payloads o errores del proveedor.

    Suficiente significa interpretación local completa, nunca elegibilidad RAG.
    No acepta instancias preconstruidas/model_construct como frontera externa.
    """
    try:
        if type(entrada) is not dict:
            raise ValueError('entrada_invalida')
        meta = EntradaInterpretacion.model_validate(entrada)
        if type(salida) is str:
            if len(salida) > 16384:
                raise ValueError('limite')
            salida = json.loads(salida, object_pairs_hook=_sin_claves_repetidas)
        if type(salida) is not dict:
            raise ValueError('salida_invalida')
        data = InterpretacionTurno.model_validate(salida)
    except (ValidationError, ValueError, TypeError, RecursionError):
        return ResultadoInterpretacion('insuficiente_o_invalida', (), None, None)

    dudas: set[Motivo] = set(data.faltantes) | set(data.contradicciones)
    hechos: dict[str, set[str]] = {}
    negadas: dict[str, set[str]] = {}
    for e in data.evidencias:
        motivo: Motivo = ('documento' if e.dimension == 'funcion_documento' else
                          'referencia' if e.dimension == 'referencia_titular' else e.dimension)
        if e.sujeto != 'objetivo' or e.origen == 'referencia_contextual':
            dudas.add('titular' if e.sujeto != 'objetivo' else motivo)
            continue
        target = negadas if e.acto == 'negacion' else hechos
        target.setdefault(e.dimension, set()).add(e.valor)
        if e.valor in {'desconocido', 'ambigua', 'varios', 'otro'}:
            dudas.add(motivo)

    for dim, values in hechos.items():
        if len(values) > 1 or values & negadas.get(dim, set()):
            dudas.add('contradiccion')
    ops = hechos.get('operacion', set())
    previo = hechos.get('dni_previo', set())
    if ('primera_vez' in ops and 'si' in previo
            or ops & {'renovacion', 'duplicado'} and 'no' in previo):
        dudas.add('dni_previo')
    # Negar un valor no afirma su alternativa. Observaciones no son solicitudes.
    solicitudes = [e for e in data.evidencias
                   if e.acto in {'solicitud_afirmativa', 'aclaracion'}
                   and e.sujeto == 'objetivo' and e.origen == 'explicito_turno']
    if not data.evidencias:
        return ResultadoInterpretacion('insuficiente_o_invalida', (), meta, data)
    if hechos.get('ambito') != {'dni'}:
        dudas.add('ambito')
    seguimiento = hechos.get('tema') == {'seguimiento'}
    if not seguimiento:
        for dim in ('titular', 'edad', 'operacion'):
            if not hechos.get(dim):
                dudas.add(dim)
        if not any(e.dimension == 'operacion' for e in solicitudes):
            dudas.add('operacion')
    elif not any(e.dimension == 'tema' and e.valor == 'seguimiento' for e in solicitudes):
        dudas.add('tema')
    estado: Estado = 'requiere_aclaracion' if dudas else 'suficiente'
    return ResultadoInterpretacion(estado, tuple(sorted(dudas)), meta, data)
