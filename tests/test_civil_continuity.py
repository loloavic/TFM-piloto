"""Regresiones de solicitud civil propia y aclaración de renovación, sin servicios."""
import pytest
from tests.test_adult_dni import motor, snapshot
from app.graph.classification import extraer_evidencia, normalizar, solicitante
from app.graph.adult_context import valor

CIVIL_QUERY = ('Soy mayor de edad y quiero actualizar mi estado civil de soltera a casada en mi DNI. '
    'Mi matrimonio fue celebrado en Perú. ¿Qué documentos debo presentar y cuánto cuesta?')


def test_reproduccion_titular_y_procedimiento_civil(motor):
    holder, explicit, conflict=solicitante(normalizar(CIVIL_QUERY))
    assert holder == {'grupo_edad':'adulto','destinatario':'propio'}
    assert explicit and not conflict
    e=extraer_evidencia(CIVIL_QUERY)
    assert e.edad == 'adulto' and e.titular == 'propio'
    service,_,_=motor
    r=service.responder(CIVIL_QUERY)
    s=snapshot(service,r['session_id'])
    assert r['intencion'] == 'dni_adulto_rectificacion'
    assert s['operacion_dni'] == 'rectificacion' and not s['requiere_aclaracion']
    assert valor(s['contexto_canonico'],'transicion') == 'matrimonio'
    assert valor(s['contexto_canonico'],'matrimonio') == 'peru'
    assert {f['archivo'] for f in r['fuentes']} == {'dni_mayor_estado_civil.txt'}


@pytest.mark.parametrize('clarification', ['seria un renuevo','Sería una renovación'])
def test_reproduccion_segundo_turno_conserva_condiciones_y_bloquea_combinacion(clarification,motor):
    service,retrieve,prompts=motor
    first=service.responder(CIVIL_QUERY)
    sid,token=first['session_id'],first['session_token']
    before=retrieve.call_count,len(prompts)
    r=service.responder(clarification,sid,token)
    s=snapshot(service,sid)
    assert s['contexto_solicitante'] == {'grupo_edad':'adulto','destinatario':'propio'}
    assert s['operacion_dni'] == 'renovacion'
    assert not s['requiere_aclaracion']
    c=s['contexto_canonico']
    assert valor(c,'modificacion') == 'estado_civil'
    assert valor(c,'transicion') == 'matrimonio' and valor(c,'matrimonio') == 'peru'
    assert not r['fuentes'] and 'no está confirmada' in r['respuesta']
    assert (retrieve.call_count,len(prompts)) == before


@pytest.mark.parametrize('question,rules,conditions', [
    (CIVIL_QUERY, {'general','matrimonio_peru'}, {'transicion':'matrimonio','matrimonio':'peru'}),
    (CIVIL_QUERY.replace('Perú','Italia'), {'general','matrimonio_extranjero'}, {'transicion':'matrimonio','matrimonio':'extranjero'}),
    ('Soy mayor de edad y quiero actualizar mi estado civil de casada a divorciada en mi DNI. '
     'Quiero recuperar el apellido materno. ¿Qué documentos debo presentar?',
     {'general','divorcio','apellido'}, {'transicion':'divorcio','apellido':'si'}),
    ('Soy mayor de edad y quiero actualizar mi estado civil de casada a viuda en mi DNI. '
     'Mi esposo falleció en Italia y era italiano. No quiero recuperar el apellido materno. '
     '¿Qué documentos debo presentar?',
     {'general','viudez_italia','italiano'}, {'transicion':'viudez','defuncion':'italia','italiano':'si','apellido':'no'}),
])
def test_casos_civiles_y_repreguntas_solo_fuente_compatible(question,rules,conditions,motor):
    service,_,_=motor
    first=service.responder(question)
    sid,token=first['session_id'],first['session_token']
    for q in ['¿Qué requisitos debo presentar?', '¿Cuánto cuesta?', '¿Dónde solicito la cita?']:
        r=service.responder(q,sid,token)
        s=snapshot(service,sid)
        c=s['contexto_canonico']
        assert s['operacion_dni'] == 'rectificacion'
        assert s['contexto_solicitante'] == {'grupo_edad':'adulto','destinatario':'propio'}
        assert {f['archivo'] for f in r['fuentes']} == {'dni_mayor_estado_civil.txt'}
        assert {f['regla'] for f in r['fuentes']} == (rules if 'requisitos' in q else {'general'})
        assert valor(c,'modificacion') == 'estado_civil'
        for key,value in conditions.items():
            assert valor(c,key) == value
            # No nombres, apellidos, lugares específicos ni texto de entrada en estas condiciones.
            d=c['condiciones_adulto'][key]
            assert set(d) == {'valor','estado','turno','revision','origen'}
            assert d['origen'] == 'explicito'


def test_cambio_a_menor_y_renovacion_adulta_sin_condiciones_heredadas(motor):
    service,_,_=motor
    first=service.responder(CIVIL_QUERY)
    sid,token=first['session_id'],first['session_token']
    r=service.responder('Ahora necesito renovar el DNI de mi hijo menor',sid,token)
    assert r['intencion'] == 'dni_menor_renovacion'
    assert not snapshot(service,sid)['contexto_canonico']['condiciones_adulto']
    assert {f['archivo'] for f in r['fuentes']} == {'dni_menor_renovacion.txt'}
    r=service.responder('Ahora quiero renovar mi DNI, soy mayor de edad',sid,token)
    assert r['intencion'] == 'dni_adulto_renovacion'
    assert not snapshot(service,sid)['contexto_canonico']['condiciones_adulto']
    assert {f['archivo'] for f in r['fuentes']} == {'dni_mayor_renovacion.txt'}


def test_negar_renovacion_no_rechaza_cambio_civil(motor):
    service,_,_=motor
    first=service.responder(CIVIL_QUERY)
    sid,token=first['session_id'],first['session_token']
    r=service.responder('No quiero renovar',sid,token)
    c=snapshot(service,sid)['contexto_canonico']
    assert c['rechazadas'] == ['renovacion']
    assert c['operacion']['valor'] == 'rectificacion'
    assert valor(c,'transicion') == 'matrimonio' and valor(c,'matrimonio') == 'peru'
    assert {f['archivo'] for f in r['fuentes']} == {'dni_mayor_estado_civil.txt'}
    r=service.responder('¿Qué documentos debo presentar?',sid,token)
    assert {f['regla'] for f in r['fuentes']} == {'general','matrimonio_peru'}


def test_pregunta_solo_por_lugar_si_es_el_unico_dato_pendiente(motor):
    service,retrieve,_=motor
    q=CIVIL_QUERY.replace('Mi matrimonio fue celebrado en Perú. ','')
    first=service.responder(q)
    sid,token=first['session_id'],first['session_token']
    before=retrieve.call_count
    r=service.responder('¿Qué requisitos debo presentar?',sid,token)
    c=snapshot(service,sid)['contexto_canonico']
    assert c['pendientes'] == {'adulto_matrimonio':'faltante'}
    assert not r['fuentes'] and retrieve.call_count == before
    assert '¿El matrimonio se celebró en Perú o fuera de Perú?' in r['respuesta']
    r=service.responder('En Italia',sid,token)
    assert {f['regla'] for f in r['fuentes']} == {'general','matrimonio_extranjero'}


@pytest.mark.parametrize('q', [
    'Soy mayor de edad y no quiero actualizar mi estado civil. ¿Debo presentar mi DNI como documento de apoyo?',
    'Soy mayor de edad y debo presentar mi DNI como documento de apoyo para el primer DNI de mi hijo menor',
])
def test_no_atribuir_actualizacion_propia_a_documento_de_apoyo(q):
    e=extraer_evidencia(q)
    assert e.edad != 'adulto'


def test_condiciones_civiles_no_se_comparten_con_otra_sesion(motor):
    service,_,_=motor
    first=service.responder(CIVIL_QUERY)
    other=service.responder('¿Qué requisitos debo presentar?')
    assert first['session_id'] != other['session_id'] and not other['fuentes']
    c=snapshot(service,other['session_id'])['contexto_canonico']
    assert not c['condiciones_adulto'] and not c['edad']['valor']
