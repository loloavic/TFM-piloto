"""Rúbrica y trazas categóricas. No participa en el recorrido operativo."""
from copy import deepcopy
import json
from pathlib import Path

from pydantic import ValidationError

from app.graph.interpretation_contract import InterpretacionTurno
from app.graph.interpretation_diagnostics import condiciones_documentales, pendientes_seguros
from app.services.interpretation_service import resumen_canonico


def cargar_referencias():
    return json.loads(Path(__file__).with_name('v2_reference_contexts.json').read_text(encoding='utf-8'))


def evidencias_seguras(model):
    if model is None:
        return []
    try:
        checked = InterpretacionTurno.model_validate(model.model_dump())
        return [e.model_dump() for e in checked.evidencias]
    except (ValidationError, AttributeError, TypeError, ValueError):
        return []


def declaraciones_seguras(model):
    if model is not None:
        try:
            checked = InterpretacionTurno.model_validate(model.model_dump())
            return dict(faltantes_declarados=list(checked.faltantes),
                        contradicciones_declaradas=list(checked.contradicciones),
                        no_mencionadas=list(checked.no_mencionadas),
                        no_aplicables=list(checked.no_aplicables))
        except (ValidationError, AttributeError, TypeError, ValueError):
            pass
    return dict(faltantes_declarados=[], contradicciones_declaradas=[],
                no_mencionadas=[], no_aplicables=[])


def clave_semantica(e, anterior):
    act = e['acto']
    # Solo hechos explícitos compatibles de ámbito/edad dentro de una solicitud.
    # Nunca normalizar negación, aclaración, operación, sujeto o procedencia.
    age_compatible = (not anterior or
        ('edad' not in anterior['pendientes'] and
         anterior['edad']['estado'] != 'conflicto' and
         anterior['edad']['valor'] in {'', e['valor']}))
    if (e['origen'] == 'explicito_turno' and e['sujeto'] == 'objetivo'
            and act in {'observacion', 'solicitud_afirmativa'}
            and (e['dimension'] == 'ambito' or e['dimension'] == 'edad' and age_compatible)):
        act = 'hecho_explicito_compatible'
    return (e['dimension'], e['valor'], act, e['origen'], e['sujeto'])


def contexto_comparable(c, *, normalizar_edad=False):
    if c is None:
        return None
    result = deepcopy(c)
    if normalizar_edad:
        result['edad'].pop('origen', None)
    return result


def evaluar_etapas(result, turno, anterior, referencia, *, edad_heredada_equivalente=False):
    atoms = evidencias_seguras(result.interpretacion)
    observed = {clave_semantica(e, anterior) for e in atoms}
    expected = {clave_semantica(e, anterior) for e in turno.evidencias_esperadas}
    semantic = bool(atoms) and result.estado == 'ok' and expected <= observed
    golden = {clave_semantica(e, anterior) for e in turno.salida_simulada['evidencias']}
    full_equivalent = (bool(atoms) and observed == golden
        and set(result.interpretacion.faltantes) == set(turno.salida_simulada['faltantes'])
        and set(result.interpretacion.contradicciones) == set(turno.salida_simulada['contradicciones']))
    # La diferencia derivada de origen canónico edad explícito/observación solo
    # se admite cuando se ha demostrado equivalencia completa de los átomos,
    # ambos son hechos nuevos de ese turno, y nunca cuando son heredados.
    after = result.contexto_canonico
    reference_after = referencia['despues'] if referencia else None
    normalize_age = bool(full_equivalent and referencia and
        any(e['dimension'] == 'edad' and e['origen'] == 'explicito_turno' for e in atoms) and
        after['edad']['turno'] == after['turno'] and
        reference_after['edad']['turno'] == reference_after['turno'])
    inherited_age = bool(edad_heredada_equivalente and anterior and referencia
        and after['edad'] == anterior['edad']
        and reference_after['edad'] == referencia['antes']['edad'])
    normalize_age = normalize_age or inherited_age
    transition = bool(referencia and
        contexto_comparable(after, normalizar_edad=normalize_age) ==
        contexto_comparable(reference_after, normalizar_edad=normalize_age))
    input_matches = bool(referencia and
        contexto_comparable(anterior, normalizar_edad=edad_heredada_equivalente) ==
        contexto_comparable(referencia['antes'], normalizar_edad=edad_heredada_equivalente))
    return dict(interpretacion_semantica_correcta=semantic,
                equivalencia_completa_fixture=full_equivalent,
                transicion_canonica_correcta=transition,
                contexto_entrada_conforme_referencia=input_matches,
                referencia_disponible=referencia is not None,
                interpretacion_semantica_evaluable=bool(atoms),
                transicion_evaluable=bool(atoms) and full_equivalent and input_matches,
                edad_origen_equivalente=normalize_age)


def _resumen_seguro(c):
    try:
        return resumen_canonico(c)
    except (TypeError, ValueError, KeyError, AttributeError):
        return {'valido': False}


def diagnostico_turno(result, anterior, referencia, etapas, documental_correcta):
    if result.interpretacion is None:
        stage = 'contrato' if result.estado == 'respuesta_invalida' else 'servicio'
    elif not etapas['interpretacion_semantica_correcta']:
        stage = 'interpretacion_o_rubrica'
    elif not etapas['referencia_disponible']:
        stage = 'referencia_no_disponible'
    elif not etapas['contexto_entrada_conforme_referencia']:
        stage = 'arrastre_previo'
    elif not etapas['transicion_canonica_correcta']:
        stage = ('transicion' if etapas['equivalencia_completa_fixture']
                 else 'interpretacion_o_transicion')
    elif not documental_correcta:
        stage = 'decision_o_expectativa'
    elif not etapas['equivalencia_completa_fixture']:
        stage = 'representacion_adicional'
    else:
        stage = 'sin_discrepancia'
    atoms = evidencias_seguras(result.interpretacion)
    witnesses = []
    if (any(e['dimension'] == 'referencia_titular' and e['valor'] == 'actual'
            and e['origen'] == 'explicito_turno' for e in atoms)
            and (anterior is None or anterior['titular']['estado'] != 'confirmado')
            and 'titular' in pendientes_seguros(result.contexto_canonico)):
        witnesses.append('referencia_actual_sin_titular_previo')
    if any(e['valor'] == 'desconocido' for e in atoms):
        witnesses.append('categoria_desconocida_emitida')
    if any(e['sujeto'] != 'objetivo' for e in atoms):
        witnesses.append('evidencia_de_sujeto_ajeno_o_no_resuelto')
    if ('tramite' in pendientes_seguros(anterior)
            and 'tramite' in pendientes_seguros(result.contexto_canonico)):
        witnesses.append('bloqueo_generico_persistente')
    # Solo códigos de este servicio; nunca copiar dicts arbitrarios al informe.
    allowed_codes = {'metadatos_invalidos', 'limite_excedido', 'tipo_invalido',
        'evidencia_vacia', 'campo_faltante', 'campo_extra', 'valor_no_permitido',
        'dimension_valor_incompatible', 'duplicado', 'tipo_o_validacion_no_clasificada',
        'json_invalido', 'clave_duplicada', 'presencia_incompatible'}
    validation = getattr(result, 'diagnostico', None) or {}
    codes = validation.get('errores_validacion', [])
    return dict(etapa_discrepancia=stage, testigos_categoricos=witnesses,

        evidencias=evidencias_seguras(result.interpretacion),
        **declaraciones_seguras(result.interpretacion),
        errores_validacion=[c for c in codes if type(c) is str and c in allowed_codes],
        pendientes_antes=pendientes_seguros(anterior),
        pendientes_despues=pendientes_seguros(result.contexto_canonico),
        canonico_antes=_resumen_seguro(anterior),
        canonico_despues=_resumen_seguro(result.contexto_canonico),
        canonico_referencia=_resumen_seguro(referencia['despues']) if referencia else None,
        condiciones_documentales=condiciones_documentales(result.contexto_canonico))
