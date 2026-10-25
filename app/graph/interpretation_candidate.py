"""V2.2E: contrato candidato 2.3-candidata-1. Sin proveedor, adaptador o rutas.

La versión activa 2.2 sigue en interpretation_contract.py. No hay conversión
implícita ni selección automática de versión. Toda incertidumbre es lingüística.
"""
from dataclasses import dataclass
import json
from typing import Generic, Literal, Self, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

T = TypeVar('T')
Origen = Literal['explicito_turno', 'referencia_contextual']
Sujeto = Literal['objetivo', 'acompanante', 'no_resuelto']


class Cerrado(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', frozen=True, revalidate_instances='always',
                              hide_input_in_errors=True)


class Hecho(Cerrado, Generic[T]):
    estado: Literal['no_mencionado', 'no_aplicable', 'determinado', 'incierto', 'contradictorio'] = 'no_mencionado'
    valor: T | None = None
    acto: Literal['solicitud_afirmativa', 'negacion', 'observacion', 'aclaracion'] | None = None
    origen: Origen | None = None
    sujeto: Sujeto | None = None

    @model_validator(mode='after')
    def consistente(self) -> Self:
        if self.estado in {'no_mencionado', 'no_aplicable'}:
            if any(v is not None for v in (self.valor, self.acto, self.origen, self.sujeto)):
                raise ValueError('presencia_incompatible')
        else:
            if self.acto is None or self.origen is None or self.sujeto is None:
                raise ValueError('procedencia_incompleta')
            if (self.estado == 'determinado') != (self.valor is not None):
                raise ValueError('valor_estado_incompatible')
        return self


class Objetivo(Cerrado):
    identificacion: Literal['no_mencionado', 'explicito_unico', 'referencia_contextual', 'multiple', 'ambiguo'] = 'no_mencionado'
    referente: Literal['ninguno', 'actual', 'otro'] = 'ninguno'

    @model_validator(mode='after')
    def consistente(self) -> Self:
        if self.identificacion == 'referencia_contextual' and self.referente != 'actual':
            raise ValueError('referencia_incompatible')
        if self.identificacion in {'no_mencionado', 'multiple', 'ambiguo'} and self.referente != 'ninguno':
            raise ValueError('referencia_incompatible')
        return self


class Soporte(Cerrado):
    origen: Origen
    sujeto: Sujeto


class ActosOperacion(Cerrado):
    # None indica ausencia del acto, nunca negación ni revocación de otro acto.
    solicitud: Soporte | None = None
    negacion: Soporte | None = None
    observacion: Soporte | None = None
    aclaracion: Soporte | None = None


class Operaciones(Cerrado):
    primera_vez: ActosOperacion = Field(default_factory=ActosOperacion)
    renovacion: ActosOperacion = Field(default_factory=ActosOperacion)
    duplicado: ActosOperacion = Field(default_factory=ActosOperacion)


class InterpretacionCandidata(Cerrado):
    version: Literal['2.3-candidata-1']
    objetivo: Objetivo = Field(default_factory=Objetivo)
    ambito: Hecho[Literal['dni', 'fuera_alcance']] = Field(default_factory=Hecho[Literal['dni', 'fuera_alcance']])
    relacion: Hecho[Literal['descendiente', 'ascendiente', 'propio', 'otra']] = Field(default_factory=Hecho[Literal['descendiente', 'ascendiente', 'propio', 'otra']])
    edad: Hecho[Literal['menor', 'adulto']] = Field(default_factory=Hecho[Literal['menor', 'adulto']])
    dni_previo: Hecho[Literal['si', 'no']] = Field(default_factory=Hecho[Literal['si', 'no']])
    tema: Hecho[Literal['requisitos', 'coste', 'plazo', 'cita', 'seguimiento', 'otra']] = Field(default_factory=Hecho[Literal['requisitos', 'coste', 'plazo', 'cita', 'seguimiento', 'otra']])
    funcion_documento: Hecho[Literal['titular', 'apoyo']] = Field(default_factory=Hecho[Literal['titular', 'apoyo']])
    operaciones: Operaciones = Field(default_factory=Operaciones)


def _objeto_unico(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError('clave_duplicada')
        obj[key] = value
    return obj


@dataclass(frozen=True)
class ValidacionCandidata:
    valida: bool
    codigo: Literal['ok', 'tipo_invalido', 'limite_excedido', 'json_invalido',
                    'clave_duplicada', 'contrato_invalido']
    estado_linguistico: Literal['no_evaluado', 'sin_evidencia', 'coherente', 'incierto', 'contradictorio']
    interpretacion: InterpretacionCandidata | None


def validar_candidata(payload: object) -> ValidacionCandidata:
    """Frontera dict/JSON. Sin confianza, suficiencia administrativa o permisos."""
    def invalid(code):
        return ValidacionCandidata(False, code, 'no_evaluado', None)
    if type(payload) is str:
        if len(payload) > 16384:
            return invalid('limite_excedido')
        try:
            payload = json.loads(payload, object_pairs_hook=_objeto_unico)
        except json.JSONDecodeError:
            return invalid('json_invalido')
        except ValueError:
            return invalid('clave_duplicada')
        except RecursionError:
            return invalid('contrato_invalido')
    if type(payload) is not dict:
        return invalid('tipo_invalido')
    try:
        data = InterpretacionCandidata.model_validate(payload)
    except (ValidationError, ValueError, TypeError, RecursionError):
        return invalid('contrato_invalido')
    facts = [data.ambito, data.relacion, data.edad, data.dni_previo,
             data.tema, data.funcion_documento]
    ops = [data.operaciones.primera_vez, data.operaciones.renovacion, data.operaciones.duplicado]
    contradictory = any(f.estado == 'contradictorio' for f in facts)
    contradictory |= any(op.solicitud is not None and op.negacion is not None
                         and op.solicitud.sujeto == op.negacion.sujeto
                         and op.solicitud.origen == op.negacion.origen == 'explicito_turno'
                         for op in ops)
    # Coexistencia no equivale a elección: no se colapsan operaciones distintas.
    requested = [op for op in ops if op.solicitud is not None]
    uncertain = data.objetivo.identificacion in {'multiple', 'ambiguo'} or len(requested) > 1
    uncertain |= any(f.estado == 'incierto' or f.sujeto == 'no_resuelto' for f in facts)
    supports = [getattr(op, k) for op in ops for k in ('solicitud', 'negacion', 'observacion', 'aclaracion')
                if getattr(op, k) is not None]
    uncertain |= any(s.sujeto == 'no_resuelto' for s in supports)
    evidence = (data.objetivo.identificacion != 'no_mencionado' or supports
                or any(f.estado not in {'no_mencionado', 'no_aplicable'} for f in facts))
    state = ('contradictorio' if contradictory else 'incierto' if uncertain else
             'coherente' if evidence else 'sin_evidencia')
    return ValidacionCandidata(True, 'ok', state, data)
