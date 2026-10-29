import copy
import pytest
from tests.test_adult_dni import motor, snapshot

INTRO='Buenas noches, ¿puedo hacer acá consultas respecto a trámites de DNI en el Consulado de Perú en Turín?'

@pytest.mark.parametrize('query,expected', [('Buenas noches','Buenas noches'),('Hola','Hola'),(INTRO,'puede consultar'),('Gracias por la información','Con gusto'),('Hasta luego','Hasta luego')])
def test_social_sin_proveedores(query,expected,motor,monkeypatch):
    service,_,prompts=motor
    def forbidden(*args,**kwargs):
        pytest.fail('Una interacción social no debe consultar proveedores')
    monkeypatch.setattr('app.graph.dni_graph.recuperar_contexto',forbidden)
    monkeypatch.setattr('app.graph.dni_graph.recuperar_reglas_exactas',forbidden)
    r=service.responder(query)
    assert expected in r['respuesta']
    assert r['fuentes']==[] and r['verificacion']=='ok' and not prompts


def test_social_conserva_contexto_y_aislamiento(motor):
    service,_,_=motor
    first=service.responder('Soy adulto y necesito renovar mi DNI')
    sid,token=first['session_id'],first['session_token']
    previous=copy.deepcopy(snapshot(service,sid)['contexto_canonico'])
    for query in ['Hola de nuevo','Gracias por la información',INTRO]:
        r=service.responder(query,sid,token)
        assert r['fuentes']==[]
        assert snapshot(service,sid)['contexto_canonico']==previous
    other=service.responder('Hola')
    assert not snapshot(service,other['session_id']).get('contexto_canonico')
    r=service.responder('¿Cuánto cuesta?',sid,token)
    assert r['intencion']=='dni_adulto_renovacion'

@pytest.mark.parametrize('query,intent',[
 ('Buenos días, necesito renovar el DNI de mi hijo menor','dni_menor_renovacion'),
 ('Hola, soy adulto y necesito renovar mi DNI','dni_adulto_renovacion'),
 ('Hola, soy adulto y necesito actualizar mi estado civil a divorciado en mi DNI','dni_adulto_rectificacion'),
 ('Hola, ¿cómo consulto el estado de mi DNI?','dni_consulta_estado'),
 ('Buenas noches, necesito información sobre pasaportes','fuera_alcance'),
])
def test_saludo_no_oculta_solicitud(query,intent,motor):
    service,_,_=motor
    r=service.responder(query)
    assert r['intencion']==intent
    assert r['respuesta'].startswith('¡')

@pytest.mark.parametrize('query',[
 'Gracias, ahora quiero consultar por otro DNI',
 'No quiero renovar mi DNI', 'No quiero saludar', 'Hola, no quiero renovarlo',
 '¿Puedo consultar sobre trámites de DNI y pasaportes?',
 'Hola, ¿cuánto cuesta?', 'Buenas tardes, ¿cómo renuevo el DNI de mi hija?',
 'Hola, ¿cuánto demora mi DNI?', '¿Puedo renovar mi DNI?',
 'Hola, necesito información', 'Hola, no',
])
def test_social_no_absorbe_material_ambiguo_o_negado(query):
    from app.graph.social import respuesta_social
    assert respuesta_social(query) is None

@pytest.mark.parametrize('query,expected',[
 ('Buenos días','Buenos días'),('Buenas tardes','Buenas tardes'),
 ('Hola de nuevo','Hola'),('Muchas gracias','Con gusto'),('Adiós','Hasta luego'),
 ('Buenas noches, ¿puedo hacer aquí consultas sobre trámites de DNI?','puede consultar'),
])
def test_formulas_controladas(query,expected):
    from app.graph.social import respuesta_social
    assert expected in respuesta_social(query)


def test_saludo_preserva_aclaracion_y_rechazos(motor):
    service,_,_=motor
    r=service.responder('Necesito renovar mi DNI')
    sid,token=r['session_id'],r['session_token']
    c=copy.deepcopy(snapshot(service,sid)['contexto_canonico'])
    service.responder('Hola',sid,token)
    assert snapshot(service,sid)['contexto_canonico']==c
    r=service.responder('mayor de edad',sid,token)
    assert r['intencion']=='dni_adulto_renovacion'
    service.responder('No quiero renovar',sid,token)
    c=copy.deepcopy(snapshot(service,sid)['contexto_canonico'])
    service.responder('Gracias',sid,token)
    assert snapshot(service,sid)['contexto_canonico']==c

@pytest.mark.parametrize('query',[
 'Hola, necesito actualizar mi estado civil a divorciado',
 'Gracias, ahora quiero consultar por otro DNI',
 'Buenas tardes, ¿cómo renuevo el DNI de mi hija?',
 'Hola, ¿cuánto demora mi DNI?',
])
def test_material_conserva_decision_del_clasificador(query,motor):
    from app.graph.classification import clasificar
    service,_,_=motor
    expected=clasificar({'pregunta':query})
    r=service.responder(query)
    assert r['intencion']==expected['intencion']
    assert not snapshot(service,r['session_id'])['respuesta_social']
