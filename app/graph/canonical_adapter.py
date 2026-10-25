"""Entrada experimental explícita por versión. No importa proveedor ni interfaz."""
from copy import deepcopy
from dataclasses import dataclass
from typing import Literal

from pydantic import ValidationError

from app.graph.canonical_delta import normalizar_candidata, normalizar_v22
from app.graph.context_policy import contexto_inicial, ruta_documental, transicionar_delta
from app.graph.interpretation_adapter import _contexto_adaptable
from app.graph.interpretation_candidate import validar_candidata
from app.graph.interpretation_contract import EntradaInterpretacion, validar_interpretacion


@dataclass(frozen=True)
class ResultadoTransicion:
    codigo: Literal['ok', 'contexto_invalido', 'vigencia_invalida', 'contrato_invalido', 'version_no_admitida', 'version_estado_incompatible', 'adaptacion_invalida']
    contexto_canonico: dict
    ruta: str
    traza: dict


def _traza(before, after):
    fields = ('objetivo', 'titular', 'edad', 'operacion', 'dni_previo', 'funcion_documento', 'relacion')
    # Solo datos cuyos valores fueron validados; ultima_ruta/textos no se copian.
    return dict(turno=after['turno'], revision=after['revision'],
        campos={field: {'antes': deepcopy(before.get(field)), 'despues': deepcopy(after.get(field))}
                for field in fields}, pendientes_antes=deepcopy(before['pendientes']),
        pendientes_despues=deepcopy(after['pendientes']),
        cambio_revision=after['revision'] != before['revision'])


def adaptar_contrato(anterior, entrada, salida, *, version) -> ResultadoTransicion:
    try:
        valid = _contexto_adaptable(anterior)
    except (TypeError, ValueError, KeyError, AttributeError):
        valid = False
    base = deepcopy(anterior) if valid and anterior is not None else contexto_inicial()
    code = 'ok'
    delta = None
    if not valid:
        code = 'contexto_invalido'
    else:
        try:
            if type(entrada) is not dict:
                raise ValueError('metadatos')
            meta = EntradaInterpretacion.model_validate(entrada)
            if meta.turno != base['turno'] + 1 or meta.revision != base['revision']:
                raise ValueError('vigencia')
        except (ValidationError, ValueError, TypeError):
            code = 'vigencia_invalida'
    if code == 'ok' and version == '2.2' and 'objetivo' in base:
        code = 'version_estado_incompatible'
    if code == 'ok':
        if version == '2.2':
            result = validar_interpretacion(entrada, salida)
            if result.interpretacion is not None:
                delta = normalizar_v22(result.interpretacion)
            else:
                code = 'contrato_invalido'
        elif version == '2.3-candidata-1':
            result = validar_candidata(salida)
            if result.valida:
                delta = normalizar_candidata(result.interpretacion)
            else:
                code = 'contrato_invalido'
        else:
            code = 'version_no_admitida'
    after = None
    if delta is not None:
        try:
            after = transicionar_delta(base, delta)
        except Exception:
            # Frontera sin excepción/payload en logs ni ruta histórica alternativa.
            code = 'adaptacion_invalida'
    if after is None:
        after = deepcopy(base)
        after['turno'] += 1
        after['retomar'] = ''
        after['pendientes']['tramite'] = 'contradiccion'
        after['consulta_pendiente'] = after['consulta_pendiente'] or after['tema']
    trace = _traza(base, after)
    trace['delta'] = delta.model_dump(mode='json') if delta is not None else None
    return ResultadoTransicion(code, after, ruta_documental(after), trace)
