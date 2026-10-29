"""Ruta civil ordinaria no equivale a una edad declarada."""
import pytest
from tests.test_adult_dni import motor, snapshot, turn
from app.graph.adult_context import valor, plan
from app.graph.context_policy import ruta_documental

GENERIC='Quiero actualizar mi estado civil en el DNI'

@pytest.mark.parametrize('prefix',['','Buenas noches, '])
def test_primero_transicion_no_edad(prefix,motor):
    service,retrieve,prompts=motor
    r=service.responder(prefix+GENERIC)
    c=snapshot(service,r['session_id'])['contexto_canonico']
    assert 'cambio necesita realizar' in r['respuesta']
    assert c['edad']['estado']=='desconocido'
    assert not r['fuentes'] and not retrieve.called and not prompts
    assert 'adulto_transicion' in c['pendientes']

@pytest.mark.parametrize('answer,transition',[
 ('de soltero a casado','matrimonio'),('a divorciado','divorcio'),('a viuda','viudez')])
def test_completa_transicion_sin_inventar_edad(answer,transition,motor):
    service,_,_=motor
    r=service.responder(GENERIC)
    r=service.responder(answer,r['session_id'],r['session_token'])
    c=snapshot(service,r['session_id'])['contexto_canonico']
    assert valor(c,'transicion')==transition
    assert c['edad']['estado']=='desconocido' and not c['edad']['valor']
    assert 'edad' not in c['pendientes']
    if transition=='divorcio':
        assert r['intencion']=='dni_adulto_rectificacion' and r['fuentes']
        assert 'solo si' in r['respuesta']
    else:
        assert c['pendientes'] and not r['fuentes']

@pytest.mark.parametrize('query',[
 'Necesito actualizar mi DNI a divorciado',
 'Mi esposo falleció en Italia y era italiano y necesito actualizar mi DNI a viuda',
])
def test_inicial_completa_sin_edad(query,motor):
    service,_,_=motor
    r=service.responder(query)
    c=snapshot(service,r['session_id'])['contexto_canonico']
    assert r['intencion']=='dni_adulto_rectificacion'
    assert {f['archivo'] for f in r['fuentes']}=={'dni_mayor_estado_civil.txt'}
    assert c['edad']['estado']=='desconocido' and not c['edad']['valor']
    assert ruta_documental(c)=='dni_adulto_rectificacion'

@pytest.mark.parametrize('query',[
 'Mi hija de 16 años necesita actualizar su estado civil en el DNI',
 'Soy menor de edad y necesito actualizar mi DNI a divorciado',
 'Necesito actualizar el DNI de mi hija a divorciada',
 'Quiero actualizar mi estado civil a casado',
 'Quiero renovar mi DNI',
 'Necesito rectificar mi fecha de nacimiento en el DNI',
])
def test_no_extiende_ruta_a_menores_terceros_u_otras_operaciones(query,motor):
    service,_,_=motor
    r=service.responder(query)
    assert not r['fuentes']
    assert r['intencion']=='general'


def test_edad_contradictoria_no_se_suple_con_ruta(motor):
    service,_,_=motor
    r=service.responder('Soy adulto y necesito actualizar mi DNI a divorciado')
    sid,token=r['session_id'],r['session_token']
    r=service.responder('Tengo 16 años',sid,token)
    c=snapshot(service,sid)['contexto_canonico']
    assert c['edad']['estado']=='conflicto' and not ruta_documental(c)
    assert not r['fuentes']
    r=service.responder('a divorciado',sid,token)
    assert not r['fuentes']

@pytest.mark.parametrize('query,answer,rule',[
 ('Quiero actualizar mi DNI de soltero a casado','Mi matrimonio se celebró en Perú','matrimonio_peru'),
 ('Quiero actualizar mi DNI de soltero a casado','Mi matrimonio se celebró en Italia','matrimonio_extranjero'),
 ('Mi esposo falleció y necesito actualizar mi DNI a viuda','Falleció en Perú','viudez_peru'),
])
def test_aclaraciones_documentales_y_repreguntas(query,answer,rule,motor):
    service,_,_=motor
    r=service.responder(query)
    sid,token=r['session_id'],r['session_token']
    assert not r['fuentes'] and 'edad' not in snapshot(service,sid)['contexto_canonico']['pendientes']
    r=service.responder(answer,sid,token)
    assert rule in {f['regla'] for f in r['fuentes']}
    for q in ['¿Cuánto cuesta?','¿Dónde solicito cita?','¿Cuánto demora?','¿Qué documentos debo presentar?']:
        r=service.responder(q,sid,token)
        assert r['intencion']=='dni_adulto_rectificacion'
        assert {f['archivo'] for f in r['fuentes']}=={'dni_mayor_estado_civil.txt'}
        assert snapshot(service,sid)['contexto_canonico']['edad']['estado']=='desconocido'


def test_cambio_titular_y_aislamiento(motor):
    service,_,_=motor
    r=service.responder('Quiero actualizar mi DNI a divorciado')
    sid,token=r['session_id'],r['session_token']
    r=service.responder('Ahora necesito renovar el DNI de mi hijo de 10 años',sid,token)
    assert r['intencion']=='dni_menor_renovacion'
    assert {f['archivo'] for f in r['fuentes']}=={'dni_menor_renovacion.txt'}
    r=service.responder('Necesito renovar mi DNI')
    assert r['intencion']=='general' and not r['fuentes']

@pytest.mark.parametrize('kind',['ausente','contradictoria'])
def test_fuente_no_valida_sigue_absteniendose(kind,motor):
    service,retrieve,_=motor
    if kind=='ausente':
        retrieve.return_value=[]
    else:
        import copy
        docs=copy.deepcopy(retrieve.return_value)
        target=next(d for d in docs if d['metadata']['archivo']=='dni_mayor_estado_civil.txt')
        target['contenido']=target['contenido'].replace('€7','€99')
        retrieve.return_value=docs
    r=service.responder('Necesito actualizar mi DNI a divorciado')
    assert not r['fuentes'] and r['verificacion'].startswith('abstencion_documental')


def test_seleccion_ruta_no_reutiliza_edad_en_renovacion(motor):
    service,_,_=motor
    r=service.responder('Necesito actualizar mi DNI a divorciado')
    r=service.responder('Ahora quiero renovar mi DNI',r['session_id'],r['session_token'])
    c=snapshot(service,r['session_id'])['contexto_canonico']
    assert c['edad']['estado']=='desconocido' and 'edad' in c['pendientes']
    assert not r['fuentes']


def test_seguimiento_sigue_siendo_de_la_ficha_civil(motor):
    service,_,_=motor
    r=service.responder('Necesito actualizar mi DNI a divorciado')
    sid,token=r['session_id'],r['session_token']
    c=snapshot(service,sid)
    assert 'ruta_ordinaria:estado_civil_sin_edad_declarada' in c['decision']['evidencias']
    r=service.responder('¿Cómo consulto el estado de mi DNI?',sid,token)
    assert {f['archivo'] for f in r['fuentes']}=={'dni_mayor_estado_civil.txt'}
    assert {f['regla'] for f in r['fuentes']}=={'seguimiento'}

@pytest.mark.parametrize('text',[
 'Soy menor de edad y me casé en Italia hace años. Necesito actualizar mi DNI a casada',
 'Mi hija de 16 años se casó en el extranjero y necesita cambiar su estado civil en el DNI',
])
def test_supuesto_historico_no_anula_minoria_explicita(text,motor):
    service,_,_=motor
    r=service.responder(text)
    assert not r['fuentes']
    c=snapshot(service,r['session_id'])['contexto_canonico']
    assert c['edad']['valor']=='menor' and not ruta_documental(c)


def test_saludo_social_y_tercero_no_heredan_ruta(motor):
    service,retrieve,prompts=motor
    r=service.responder('Buenas noches')
    assert not retrieve.called and not prompts
    r=service.responder('Quiero actualizar mi estado civil en el DNI',r['session_id'],r['session_token'])
    assert 'cambio necesita realizar' in r['respuesta']
    r=service.responder('Ahora es para el DNI de mi hija',r['session_id'],r['session_token'])
    assert not r['fuentes']
    assert not ruta_documental(snapshot(service,r['session_id'])['contexto_canonico'])
