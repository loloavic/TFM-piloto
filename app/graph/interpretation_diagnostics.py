"""Observaciones de evaluación por whitelist; no cambia validación ni autorización."""
import json

from pydantic import ValidationError

from app.graph.context_policy import PRIORIDAD, DOCUMENTADOS, tramite_candidato, validar_contexto
from app.graph.interpretation_contract import (
    EntradaInterpretacion, InterpretacionTurno, _sin_claves_repetidas,
)


def diagnosticar_validacion(entrada, salida):
    """Nunca retornar input, msg, ctx o propiedades arbitrarias de ValidationError."""
    try:
        if type(entrada) is not dict:
            return ['metadatos_invalidos']
        EntradaInterpretacion.model_validate(entrada)
    except (ValidationError, ValueError, TypeError):
        return ['metadatos_invalidos']
    try:
        if type(salida) is str:
            if len(salida) > 16384:
                return ['limite_excedido']
            salida = json.loads(salida, object_pairs_hook=_sin_claves_repetidas)
        if type(salida) is not dict:
            return ['tipo_invalido']
        model = InterpretacionTurno.model_validate(salida)
        return [] if model.evidencias else ['evidencia_vacia']
    except ValidationError as error:
        codes = set()
        for item in error.errors(include_input=False, include_url=False):
            code = {'missing': 'campo_faltante', 'extra_forbidden': 'campo_extra',
                    'literal_error': 'valor_no_permitido', 'too_long': 'limite_excedido',
                    'too_short': 'evidencia_vacia'}.get(item['type'])
            if code is None and item['type'] == 'value_error':
                # Mensajes de validadores locales conocidos; jamás serializar ctx.
                message = str(item.get('ctx', {}).get('error', ''))
                code = {'valor_incompatible': 'dimension_valor_incompatible',
                        'duplicados': 'duplicado', 'presencia_incompatible': 'presencia_incompatible'}.get(message)
            codes.add(code or 'tipo_o_validacion_no_clasificada')
        return sorted(codes)
    except json.JSONDecodeError:
        return ['json_invalido']
    except ValueError:
        return ['clave_duplicada']
    except (TypeError, RecursionError):
        return ['tipo_o_validacion_no_clasificada']


def pendientes_seguros(c):
    if not isinstance(c, dict):
        return {}
    pending = c.get('pendientes')
    if not isinstance(pending, dict):
        return {}
    return {key: pending[key] for key in PRIORIDAD
            if type(pending.get(key)) is str and pending[key] in {'faltante', 'contradiccion'}}


def condiciones_documentales(c):
    """Explica condiciones vigentes, sin sustituir ruta_documental."""
    valid = isinstance(c, dict) and validar_contexto(c)
    if not valid:
        return [{'condicion': 'contexto_valido', 'aplica': True, 'cumplida': False}]
    followup = c['tema'] == 'seguimiento'
    operation = c['operacion']
    age_required = not followup and operation['valor'] in {'primera_vez', 'renovacion'}
    return [dict(condicion=key, aplica=applies, cumplida=bool(ok)) for key, applies, ok in (
        ('contexto_valido', True, True),
        ('ambito_dni', True, c['ambito'] == 'dni'),
        ('sin_pendientes', True, not c['pendientes']),
        ('operacion_confirmada', not followup, operation['estado'] == 'confirmado'),
        ('operacion_no_rechazada', not followup, operation['valor'] not in c['rechazadas']),
        ('edad_confirmada', age_required, c['edad']['estado'] == 'confirmado'),
        ('procedimiento_documentado', True,
         followup or tramite_candidato(c) in DOCUMENTADOS),
    )]
