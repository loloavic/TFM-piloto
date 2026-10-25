"""Entrada V2 desacoplada: valida contrato/vigencia y delega en política canónica."""
from copy import deepcopy

from app.graph.context_policy import (
    contexto_inicial, transicionar_v2, validar_contexto,
)
from app.graph.interpretation_contract import validar_interpretacion


def _contexto_adaptable(c):
    if c is None:
        return True
    allowed = set(contexto_inicial()) | {'dni_previo', 'funcion_documento', 'relacion'}
    if type(c) is not dict or set(c) - allowed or not validar_contexto(c):
        return False
    if any(type(c[k]) is not int for k in ('turno', 'revision')):
        return False
    for field in ('titular', 'edad', 'operacion', 'dni_previo', 'funcion_documento', 'relacion'):
        if field not in c:
            continue
        d = c[field]
        if (type(d) is not dict or set(d) != {'valor', 'estado', 'turno', 'revision', 'origen'}
                or any(type(d[k]) is not int for k in ('turno', 'revision'))):
            return False
    return True


def adaptar_interpretacion(anterior: dict | None, entrada: object, salida: object) -> dict:
    """Devuelve solo contexto canónico, sin ruta, payload, historial o proveedor.

    entrada procede del llamador: turno siguiente y revisión actual. Nunca usar
    metadatos producidos por el LLM. Una respuesta obsoleta bloquea el turno.
    """
    try:
        valido = _contexto_adaptable(anterior)
    except (TypeError, AttributeError):
        valido = False
    base = deepcopy(anterior) if valido and anterior is not None else contexto_inicial()
    resultado = validar_interpretacion(entrada, salida)
    meta = resultado.entrada
    if (not valido or resultado.interpretacion is None
            or not resultado.interpretacion.evidencias or meta is None
            or meta.turno != base['turno'] + 1 or meta.revision != base['revision']):
        base['turno'] += 1
        base['retomar'] = ''
        base['pendientes']['tramite'] = 'contradiccion'
        base['consulta_pendiente'] = base['consulta_pendiente'] or base['tema']
        return base
    # No se usa el estado local de suficiencia como permiso ni como veto a
    # referencias resolubles. La política evalúa la evidencia contra el canónico.
    try:
        return transicionar_v2(base, resultado.interpretacion)
    except (ValueError, TypeError, KeyError, AttributeError):
        # Frontera sin payload ni fallback documental ante fallo de adaptación.
        base['turno'] += 1
        base['retomar'] = ''
        base['pendientes']['tramite'] = 'contradiccion'
        base['consulta_pendiente'] = base['consulta_pendiente'] or base['tema']
        return base
