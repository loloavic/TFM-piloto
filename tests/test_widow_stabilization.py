"""Fase A: apellido, completitud y diagnóstico de recuperación; sin servicios reales."""
import pytest
from tests.test_adult_dni import motor, snapshot
from tests.test_widow_answers import WIDOW
from app.graph.adult_context import valor


@pytest.mark.parametrize('answer', ['no','No, ya utilizo mi apellido materno',
    'no, he mantenido siempre mi apellido materno','No necesito cambiar mi apellido'])
def test_apellido_negativo_resuelve_y_preserva_viudez(answer,motor):
    service,_,_=motor
    first=service.responder(WIDOW)
    sid,token=first['session_id'],first['session_token']
    for q in [answer,'no']:
        r=service.responder(q,sid,token)
        c=snapshot(service,sid)['contexto_canonico']
        assert valor(c,'apellido') == ('' if answer == 'no' else 'no') and not c['pendientes']
        assert c['edad']['valor'] == 'adulto'
        assert valor(c,'italiano') == 'si' and valor(c,'defuncion') == 'italia'
        assert valor(c,'transicion') == 'viudez'
        assert {f['regla'] for f in r['fuentes']} == ({'general','viudez_italia','italiano','apellido'} if answer == 'no' else {'general','viudez_italia','italiano'})
        assert 'OBSERVACIÓN PENDIENTE' not in r['respuesta']
        assert 'acta de defunción plurilingüe' in r['respuesta']


def test_regla_ausente_diagnosticada_no_es_ok(motor):
    service,retrieve,prompts=motor
    retrieve.return_value=[d for d in retrieve.return_value if not d['contenido'].startswith('[[REGLA:italiano]]')]
    first=service.responder(WIDOW)
    r=service.responder('No quiero recuperar el apellido materno',first['session_id'],first['session_token'])
    s=snapshot(service,first['session_id'])
    assert s['reglas_faltantes'] == ['dni_mayor_estado_civil.txt#italiano']
    assert not r['fuentes'] and not prompts
    assert r['verificacion'].startswith('abstencion_documental:')
    assert 'no' == valor(s['contexto_canonico'],'apellido')


@pytest.mark.parametrize('transition,italian', [('divorcio',False),('viudez',True),('viudez',False)])
@pytest.mark.parametrize('answer,value', [('Sí, quiero recuperar mi apellido materno','si'),
    ('No, ya utilizo mi apellido materno','no')])
def test_apellido_afirmativo_negativo_por_caso(transition,italian,answer,value,motor):
    service,_,_=motor
    query=('Soy adulto y quiero cambiar mi estado civil en mi DNI. Me divorcié' if transition == 'divorcio'
           else WIDOW if italian else WIDOW.replace('era ciudadano italiano','no era italiano'))
    first=service.responder(query)
    r=service.responder(answer,first['session_id'],first['session_token'])
    c=snapshot(service,first['session_id'])['contexto_canonico']
    assert valor(c,'apellido') == value and not c['pendientes']
    expected={'general', 'divorcio' if transition == 'divorcio' else 'viudez_italia'}
    if italian: expected.add('italiano')
    if value == 'si': expected.add('apellido')
    assert {f['regla'] for f in r['fuentes']} == expected


def test_reintento_recupera_regla_omitida_por_top_k_sin_cambiar_plan(motor):
    service,retrieve,_=motor
    complete=retrieve.return_value
    initial=[d for d in complete if not d['contenido'].startswith('[[REGLA:italiano]]')]
    retrieve.side_effect=[initial,complete]
    first=service.responder(WIDOW + ' No quiero recuperar el apellido materno.')
    r=first
    assert retrieve.call_count == 2
    assert 'dni_mayor_estado_civil.txt REGLA italiano' in retrieve.call_args.args[0]
    assert {f['regla'] for f in r['fuentes']} == {'general','viudez_italia','italiano'}
    assert not snapshot(service,first['session_id'])['reglas_faltantes']


def test_contradiccion_apellido_y_correccion(motor):
    service,retrieve,_=motor
    first=service.responder(WIDOW)
    sid,token=first['session_id'],first['session_token']
    retrieve.reset_mock()
    r=service.responder('No necesito cambiar mi apellido. Quiero recuperar mi apellido materno',sid,token)
    c=snapshot(service,sid)['contexto_canonico']
    assert c['pendientes']['adulto_apellido'] == 'contradiccion' and not retrieve.called
    r=service.responder('No, he mantenido siempre mi apellido materno',sid,token)
    assert valor(snapshot(service,sid)['contexto_canonico'],'apellido') == 'no' and r['fuentes']


def test_cambios_y_repreguntas_no_reabren_apellido_ni_comparten_contexto(motor):
    service,_,_=motor
    first=service.responder(WIDOW)
    sid,token=first['session_id'],first['session_token']
    service.responder('No necesito cambiar mi apellido',sid,token)
    for q in ['¿Qué requisitos debo presentar?','¿Cuánto cuesta?','¿Dónde solicito la cita?']:
        r=service.responder(q,sid,token)
        assert r['fuentes'] and valor(snapshot(service,sid)['contexto_canonico'],'apellido') == 'no'
    other=service.responder('no')
    assert not snapshot(service,other['session_id'])['contexto_canonico']['condiciones_adulto']
    r=service.responder('Ahora quiero renovar el DNI de mi hijo menor',sid,token)
    assert r['intencion'] == 'dni_menor_renovacion'
    assert not snapshot(service,sid)['contexto_canonico']['condiciones_adulto']


def test_fuentes_ausentes_diagnostican_todas_las_reglas(motor):
    service,retrieve,_=motor
    retrieve.return_value=[]
    first=service.responder(WIDOW)
    r=first
    s=snapshot(service,first['session_id'])
    assert s['reglas_faltantes'] == ['dni_mayor_estado_civil.txt#apellido','dni_mayor_estado_civil.txt#general',
        'dni_mayor_estado_civil.txt#italiano','dni_mayor_estado_civil.txt#viudez_italia']
    assert not r['fuentes'] and r['verificacion'].startswith('abstencion_documental:')
    assert retrieve.call_count == 5  # consulta inicial + cuatro reglas, sin bucle
