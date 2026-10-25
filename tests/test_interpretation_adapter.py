from copy import deepcopy

import pytest

from app.graph.context_policy import contexto_inicial, ruta_documental, validar_contexto
from app.graph.interpretation_adapter import adaptar_interpretacion


def e(dim, value, act='observacion', origin='explicito_turno', subject='objetivo'):
    return dict(dimension=dim, valor=value, acto=act, origen=origin, sujeto=subject)


def packet(*items, missing=(), conflicts=()):
    return dict(version='2.1', evidencias=list(items), faltantes=list(missing),
                contradicciones=list(conflicts))


def turn(c, *items, **kwargs):
    base = c or contexto_inicial()
    result = adaptar_interpretacion(c, dict(turno=base['turno'] + 1,
        revision=base['revision']), packet(*items, **kwargs))
    assert validar_contexto(result)
    return result


def request(op='renovacion', age='menor', holder='descendiente'):
    return [e('ambito', 'dni'), e('titular', holder, 'solicitud_afirmativa'),
            e('edad', age, 'solicitud_afirmativa'),
            e('operacion', op, 'solicitud_afirmativa'), e('tema', 'requisitos')]


def base(op='renovacion'):
    return turn(None, *request(op))


@pytest.mark.parametrize('op,topic,route', [
    ('renovacion', 'coste', 'dni_menor_renovacion'),
    ('primera_vez', 'cita', 'dni_menor_primera_vez'),
])
def test_repregunta_hereda_sin_convertir_en_evidencia_nueva(op, topic, route):
    c = base(op)
    before = deepcopy(c)
    n = turn(c, e('tema', topic, 'solicitud_afirmativa'))
    assert ruta_documental(n) == route
    for dim in ('edad', 'titular', 'operacion'):
        assert n[dim] == c[dim]
    assert c == before


def test_rechazo_titular_y_observacion_no_rehabilitan():
    c = turn(base(), e('operacion', 'renovacion', 'negacion'))
    c = turn(c, e('titular', 'descendiente', 'aclaracion'))
    assert 'renovacion' in c['rechazadas'] and not ruta_documental(c)
    c = turn(c, e('operacion', 'renovacion'))
    assert 'renovacion' in c['rechazadas'] and not ruta_documental(c)
    c = turn(c, e('operacion', 'renovacion', 'solicitud_afirmativa'))
    assert not c['rechazadas'] and ruta_documental(c) == 'dni_menor_renovacion'


def test_funcion_documental_se_resuelve_solo_con_dimension_pertinente():
    c = turn(base(), e('funcion_documento', 'ambigua'))
    c = turn(c, e('edad', 'menor', 'aclaracion'))
    assert 'documento' in c['pendientes'] and not ruta_documental(c)
    c = turn(c, e('funcion_documento', 'apoyo', 'aclaracion'))
    assert c['funcion_documento']['valor'] == 'apoyo'
    assert ruta_documental(c) == 'dni_menor_renovacion'
    assert c['titular']['valor'] == 'descendiente'


def test_titular_adulto_explicito_sin_documentacion():
    c = base()
    n = turn(c, *request(age='adulto', holder='adulto'),
             e('referencia_titular', 'otro', 'solicitud_afirmativa'))
    assert n['revision'] == c['revision'] + 1
    assert n['edad']['valor'] == 'adulto' and n['operacion']['valor'] == 'renovacion'
    assert not n['pendientes'] and not ruta_documental(n)


@pytest.mark.parametrize('value', ['varios', 'ambigua'])
def test_dos_titulares_y_referencia_ambigua_no_heredan(value):
    c = turn(base(), e('referencia_titular', value))
    assert not ruta_documental(c) and not c['edad']['valor']
    c = turn(c, e('titular', 'descendiente', origin='referencia_contextual'))
    assert 'titular' in c['pendientes'] and not ruta_documental(c)


def test_edad_contradictoria_aclaracion_insuficiente_y_resolucion():
    c = turn(base(), e('edad', 'adulto'))
    assert 'edad' in c['pendientes'] and not ruta_documental(c)
    c = turn(c, e('titular', 'descendiente', 'aclaracion'))
    c = turn(c, e('edad', 'menor', origin='referencia_contextual'))
    assert 'edad' in c['pendientes'] and not ruta_documental(c)
    c = turn(c, e('edad', 'menor', 'aclaracion'))
    assert ruta_documental(c) == 'dni_menor_renovacion'


@pytest.mark.parametrize('dim,value', [('edad', 'menor'), ('operacion', 'renovacion'),
                                      ('titular', 'descendiente'), ('ambito', 'dni'),
                                      ('referencia_titular', 'actual')])
def test_referencia_compatible_no_renueva_procedencia(dim, value):
    c = base()
    n = turn(c, e(dim, value, origin='referencia_contextual'), e('tema', 'coste'))
    assert ruta_documental(n) == 'dni_menor_renovacion'
    for field in ('edad', 'titular', 'operacion'):
        assert n[field] == c[field]


@pytest.mark.parametrize('dim,value', [('edad', 'adulto'), ('operacion', 'primera_vez'),
                                      ('titular', 'adulto'), ('tema', 'cita')])
def test_referencia_incompatible_bloquea(dim, value):
    c = turn(base(), e(dim, value, origin='referencia_contextual'))
    assert not ruta_documental(c)


def test_cambio_misma_categoria_invalida_datos_y_referencias():
    c = turn(base(), e('referencia_titular', 'otro', 'solicitud_afirmativa'),
             e('titular', 'descendiente', 'solicitud_afirmativa'),
             e('edad', 'menor', origin='referencia_contextual'))
    assert not c['edad']['valor'] and not c['operacion']['valor']
    assert not ruta_documental(c)


@pytest.mark.parametrize('act', ['negacion', 'observacion'])
def test_primera_operacion_no_afirmativa_no_autoriza(act):
    items = request()
    items[3]['acto'] = act
    assert not ruta_documental(turn(None, *items))


@pytest.mark.parametrize('payload', [None, {}, 'invalid', [], packet(),
    dict(version='2.1', evidencias=[], faltantes=[], contradicciones=[], confianza=1)])
def test_salida_invalida_bloquea_ruta_historica(payload):
    c = base()
    n = adaptar_interpretacion(c, dict(turno=2, revision=0), payload)
    assert validar_contexto(n) and not ruta_documental(n)
    n = turn(n, e('tema', 'coste'))
    assert not ruta_documental(n)


def test_incompleta_sin_contexto_no_autoriza():
    assert not ruta_documental(turn(None, e('tema', 'coste')))


@pytest.mark.parametrize('meta', [dict(turno=1, revision=0), dict(turno=2, revision=1),
                                   dict(turno=True, revision=0)])
def test_vigencia(meta):
    n = adaptar_interpretacion(base(), meta, packet(*request()))
    assert not ruta_documental(n)


@pytest.mark.parametrize('old', [{}, {'turno': 1}, {'pendientes': None}])
def test_contexto_invalido_no_se_reconstruye_desde_etiquetas(old):
    n = adaptar_interpretacion(old, dict(turno=1, revision=0), packet(*request()))
    assert validar_contexto(n) and not ruta_documental(n)


def test_tenencia_persiste_y_bloquea_operacion_incompatible_posterior():
    c = turn(base('primera_vez'), e('dni_previo', 'no'))
    c = turn(c, e('operacion', 'renovacion', 'solicitud_afirmativa'))
    assert 'dni_previo' in c['pendientes'] and not ruta_documental(c)
    c = turn(c, e('tema', 'coste'))
    assert not ruta_documental(c)
    c = turn(c, e('dni_previo', 'si', 'aclaracion'))
    assert ruta_documental(c) == 'dni_menor_renovacion'


def test_contradiccion_local_no_se_resuelve_por_orden():
    for items in ([e('edad', 'menor'), e('edad', 'adulto')],
                  [e('edad', 'adulto'), e('edad', 'menor')]):
        c = turn(base(), *items)
        assert not ruta_documental(c)
        c = turn(c, e('edad', 'menor', 'aclaracion'))
        assert ruta_documental(c)


def test_observacion_no_resuelve_conflicto_de_tenencia():
    c = turn(base(), e('dni_previo', 'no'))
    c = turn(c, e('dni_previo', 'si'))
    assert not ruta_documental(c)


def test_seguimiento_con_contexto_validado():
    c = turn(base(), e('tema', 'seguimiento', 'solicitud_afirmativa'))
    assert ruta_documental(c) == 'dni_consulta_estado'
    c = turn(c, e('edad', 'adulto'), e('tema', 'seguimiento'))
    assert not ruta_documental(c)


@pytest.mark.parametrize('reason', ['ambito', 'tema', 'referencia', 'documento', 'dni_previo'])
def test_dimensiones_declaradas_no_se_descartan(reason):
    assert not ruta_documental(turn(base(), e('tema', 'coste'), conflicts=[reason]))


def test_estructura_unica_y_aislamiento():
    c = base()
    assert set(c) == set(contexto_inicial()) | {'dni_previo', 'funcion_documento'}
    assert 'evidencias' not in c and 'historial' not in c
    n = turn(c, e('operacion', 'renovacion', 'negacion'))
    assert ruta_documental(c) and not ruta_documental(n)


def test_rechazo_sobrevive_referencia_ambigua():
    c = turn(base(), e('operacion', 'renovacion', 'negacion'))
    c = turn(c, e('referencia_titular', 'ambigua'))
    assert 'renovacion' in c['rechazadas']
    c = turn(c, e('titular', 'descendiente', 'aclaracion'),
             e('edad', 'menor', 'aclaracion'), e('operacion', 'renovacion'))
    assert 'renovacion' in c['rechazadas'] and not ruta_documental(c)


def test_observacion_seguimiento_no_inicia_solicitud():
    assert not ruta_documental(turn(None, e('ambito', 'dni'), e('tema', 'seguimiento')))
    assert ruta_documental(turn(None, e('ambito', 'dni'),
        e('tema', 'seguimiento', 'solicitud_afirmativa'))) == 'dni_consulta_estado'


def test_referencia_actual_sin_titular_no_autoriza():
    c = turn(None, e('ambito', 'dni'), e('referencia_titular', 'actual'),
             e('tema', 'seguimiento', 'solicitud_afirmativa'))
    assert not ruta_documental(c)


def test_fallo_de_transicion_no_devuelve_ruta_historica(monkeypatch):
    import app.graph.interpretation_adapter as adapter
    def fail(*args):
        raise ValueError('NO_LOG_PAYLOAD')
    monkeypatch.setattr(adapter, 'transicionar_v2', fail)
    n = adaptar_interpretacion(base(), dict(turno=2, revision=0), packet(*request()))
    assert not ruta_documental(n) and 'NO_LOG_PAYLOAD' not in repr(n)


@pytest.mark.parametrize('field', ['dni_previo', 'funcion_documento'])
def test_extension_canonicamente_corrupta_bloquea(field):
    c = base()
    c[field]['turno'] = True
    assert not validar_contexto(c) and not ruta_documental(c)


def test_contexto_con_campos_inesperados_no_persiste_identidades():
    c = base()
    c['identidad'] = 'PERSONA_SINTETICA'
    n = adaptar_interpretacion(c, dict(turno=2, revision=0), packet(*request()))
    assert not ruta_documental(n) and 'PERSONA_SINTETICA' not in repr(n)


def test_referencia_a_dato_vigente_no_valida_afirmacion_incompatible_del_turno():
    c = turn(base(), e('edad', 'menor', origin='referencia_contextual'),
             e('edad', 'adulto', 'aclaracion'))
    assert 'edad' in c['pendientes'] and not ruta_documental(c)


def test_dimensiones_ajenas_no_actualizan_edad_del_objetivo():
    c = turn(base(), e('edad', 'adulto', subject='otro'))
    assert 'titular' in c['pendientes'] and c['edad']['valor'] == ''
    assert not ruta_documental(c)


def test_rechazo_y_afirmacion_mismo_turno_bloquean():
    c = turn(base(), e('operacion', 'renovacion', 'negacion'),
             e('operacion', 'renovacion', 'solicitud_afirmativa'))
    assert 'renovacion' in c['rechazadas'] and not ruta_documental(c)


def test_entrada_directa_politica_vacia_tambien_bloquea():
    from app.graph.context_policy import transicionar_v2
    from app.graph.interpretation_contract import InterpretacionTurno
    c = transicionar_v2(base(), InterpretacionTurno.model_validate(packet()))
    assert validar_contexto(c) and not ruta_documental(c)
