"""Nacionalidad contextual y validación de respuestas breves sin OpenAI."""
import pytest
from tests.test_adult_dni import motor, snapshot
from app.graph.adult_context import valor

WIDOW = ('Soy mayor de edad y necesito cambiar mi estado civil de casada a viuda en mi DNI. '
         'Mi esposo falleció en Italia y era ciudadano italiano. ¿Qué documentos debo presentar?')
PENDING = ('Soy mayor de edad y necesito cambiar mi estado civil de casada a viuda en mi DNI. '
           'Mi esposo falleció en Italia. No quiero recuperar el apellido materno. ¿Qué documentos debo presentar?')


def test_consulta_completa_reconoce_ciudadano_italiano(motor):
    service,_,_=motor
    r=service.responder(WIDOW)
    c=snapshot(service,r['session_id'])['contexto_canonico']
    assert valor(c,'italiano') == 'si'
    assert 'adulto_italiano' not in c['pendientes']


@pytest.mark.parametrize('answer,value', [
    ('sí','si'), ('si','si'), ('no','no'), ('si era italiano','si'),
    ('Sí, era italiano','si'), ('Era italiano','si'),
    ('era ciudadano italiano','si'), ('no, era peruano','no'),
])
def test_confirmaciones_ampliadas_resuelven_pendiente(answer,value,motor):
    service,_,_=motor
    first=service.responder(PENDING)
    r=service.responder(answer,first['session_id'],first['session_token'])
    c=snapshot(service,first['session_id'])['contexto_canonico']
    assert valor(c,'italiano') == value and not c['pendientes']
    assert {f['regla'] for f in r['fuentes']} == ({'general','viudez_italia','italiano'} if value == 'si' else {'general','viudez_italia'})
    assert ('No puedo confirmar' in r['respuesta']) == (value == 'no')


@pytest.mark.parametrize('answer', ['sí','si','no'])
def test_api_y_gradio_aceptan_respuesta_breve_con_credencial(answer,motor,monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app import ui
    service,_,_=motor
    monkeypatch.setattr(ui,'rag',service)
    with TestClient(app) as client:
        first=client.post('/api/v1/consultas',json={'pregunta':PENDING})
        sid,token=first.json()['session_id'],first.headers['X-Session-Token']
        r=client.post('/api/v1/consultas',json={'pregunta':answer,'session_id':sid},headers={'X-Session-Token':token})
        assert r.status_code == 200 and r.json()['fuentes']
    initial=ui.responder_consulta(PENDING,[],ui.generar_session_id())
    result=ui.responder_consulta(answer,[],initial[2])
    assert result[1][-1]['role'] == 'assistant'
    assert ('No puedo confirmar' in result[1][-1]['content']) == (answer == 'no')


@pytest.mark.parametrize('statement', [
    'Mi esposo era italiano', 'Mi esposo era ciudadano italiano',
    'Mi esposo era de nacionalidad italiana', 'Mi cónyuge era italiano',
])
def test_afirmacion_completa_nacionalidad_no_pregunta_de_nuevo(statement,motor):
    service,_,_=motor
    r=service.responder(PENDING + ' ' + statement)
    c=snapshot(service,r['session_id'])['contexto_canonico']
    assert valor(c,'italiano') == 'si' and not c['pendientes']
    assert {f['regla'] for f in r['fuentes']} == {'general','viudez_italia','italiano'}


@pytest.mark.parametrize('text', ['', ' ', 'a','1','?', 'ab','ok', '...', ' '*3, 'x'*1001])
def test_validacion_equivalente_api_gradio_rechaza_entradas_invalidas(text,motor,monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app import ui
    from app.core.query_validation import ERROR_CONSULTA
    service,retrieve,_=motor
    monkeypatch.setattr(ui,'rag',service)
    with TestClient(app) as client:
        assert client.post('/api/v1/consultas',json={'pregunta':text}).status_code == 422
    r=ui.responder_consulta(text,[],ui.generar_session_id())
    assert r[-1] == ERROR_CONSULTA and not r[1] and not retrieve.called


@pytest.mark.parametrize('answer,value', [('sí','si'),('no','no')])
def test_binaria_otra_aclaracion_no_se_atribuye_a_nacionalidad(answer,value,motor):
    service,_,_=motor
    first=service.responder('Soy adulto y quiero cambiar el estado civil en mi DNI. Me divorcié. '
                            'No necesito cambiar mi apellido. Quiero recuperar mi apellido materno')
    assert snapshot(service,first['session_id'])['contexto_canonico']['pendientes']['adulto_apellido'] == 'contradiccion'
    r=service.responder(answer,first['session_id'],first['session_token'])
    c=snapshot(service,first['session_id'])['contexto_canonico']
    assert valor(c,'apellido') == value and not valor(c,'italiano')
    assert {f['regla'] for f in r['fuentes']} == ({'general','divorcio','apellido'} if value == 'si' else {'general','divorcio'})


def test_nacionalidad_confirmada_correccion_explicita_y_continuidad(motor):
    service,_,_=motor
    first=service.responder(PENDING + ' Mi esposo era italiano')
    sid,token=first['session_id'],first['session_token']
    r=service.responder('Me equivoqué, no era italiano',sid,token)
    c=snapshot(service,sid)['contexto_canonico']
    assert valor(c,'italiano') == 'no'
    assert valor(c,'transicion') == 'viudez' and valor(c,'defuncion') == 'italia'
    assert c['edad']['valor'] == 'adulto'
    assert {f['regla'] for f in r['fuentes']} == {'general','viudez_italia'}
    r=service.responder('¿Qué documentos debo presentar?',sid,token)
    assert {f['regla'] for f in r['fuentes']} == {'general','viudez_italia'}
    assert 'No puedo confirmar' in r['respuesta']


def test_contradiccion_no_se_resuelve_por_cambio_a_tasas(motor):
    service,retrieve,_=motor
    first=service.responder(PENDING + ' Mi esposo era italiano y mi esposo no era italiano')
    sid,token=first['session_id'],first['session_token']
    c=snapshot(service,sid)['contexto_canonico']
    assert c['pendientes']['adulto_italiano'] == 'contradiccion'
    assert not retrieve.called
    r=service.responder('¿Cuánto cuesta?',sid,token)
    assert not r['fuentes'] and not retrieve.called
    r=service.responder('No era italiano',sid,token)
    assert {f['regla'] for f in r['fuentes']} == {'general'}  # retoma coste
    assert valor(snapshot(service,sid)['contexto_canonico'],'italiano') == 'no'


@pytest.mark.parametrize('answer', ['sí','no','Era italiano'])
def test_sin_contexto_no_confirma_nacionalidad(answer,motor):
    service,retrieve,_=motor
    r=service.responder(answer)
    assert not r['fuentes'] and not retrieve.called
    assert not snapshot(service,r['session_id'])['contexto_canonico']['condiciones_adulto']


def test_nacionalidad_de_otra_persona_no_es_del_conyuge(motor):
    service,retrieve,_=motor
    r=service.responder(PENDING + ' Mi padre era italiano')
    c=snapshot(service,r['session_id'])['contexto_canonico']
    assert not valor(c,'italiano') and 'adulto_italiano' in c['pendientes']
    assert not retrieve.called


def test_cambio_titular_y_otro_navegador_no_heredan_viudez(motor):
    service,_,_=motor
    first=service.responder(PENDING + ' Mi esposo era italiano')
    sid,token=first['session_id'],first['session_token']
    r=service.responder('Ahora quiero renovar el DNI de mi hijo menor',sid,token)
    assert r['intencion'] == 'dni_menor_renovacion'
    assert not snapshot(service,sid)['contexto_canonico']['condiciones_adulto']
    fresh=service.responder('sí')
    assert not fresh['fuentes'] and fresh['session_id'] != sid
    assert not snapshot(service,fresh['session_id'])['contexto_canonico']['condiciones_adulto']


def test_respuesta_breve_no_elude_credencial_api(motor):
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        first=client.post('/api/v1/consultas',json={'pregunta':PENDING})
        sid=first.json()['session_id']
        assert client.post('/api/v1/consultas',json={'pregunta':'sí','session_id':sid}).status_code == 403


def test_consulta_completa_solo_pregunta_por_el_dato_realmente_pendiente(motor):
    service,_,_=motor
    first=service.responder(WIDOW)
    sid,token=first['session_id'],first['session_token']
    for q in ['si era italiano','Sí, era italiano']:
        r=service.responder(q,sid,token)
        c=snapshot(service,sid)['contexto_canonico']
        assert not c['pendientes'] and not valor(c,'apellido')
        assert valor(c,'italiano') == 'si'
        assert '¿Desea recuperar el apellido materno?' not in r['respuesta']
        assert 'solo si' in r['respuesta']
    r=service.responder('sí',sid,token)
    assert {f['regla'] for f in r['fuentes']} == {'general','viudez_italia','italiano','apellido'}


def test_regla_italiano_ausente_abstiene_sin_reabrir_confirmacion(motor):
    service,retrieve,prompts=motor
    retrieve.return_value=[d for d in retrieve.return_value if not d['contenido'].startswith('[[REGLA:italiano]]')]
    r=service.responder(PENDING + ' Mi esposo era ciudadano italiano')
    c=snapshot(service,r['session_id'])['contexto_canonico']
    assert valor(c,'italiano') == 'si' and not c['pendientes']
    assert not r['fuentes'] and not prompts
    assert 'No cuento con información documental suficiente' in r['respuesta']
