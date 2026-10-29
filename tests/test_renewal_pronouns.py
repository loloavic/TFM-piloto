"""Operación con pronombre y vigencia explícita, sin proveedor real."""
import pytest
from app.graph.classification import clasificar, extraer_evidencia
from app.graph.adult_context import valor
from tests.test_adult_dni import motor, snapshot

@pytest.mark.parametrize('days',[59,60,61])
def test_reproduccion_gradio(days,motor):
    service,_,prompts=motor
    q=f'Soy mayor de edad y mi DNI vence dentro de {days} días. ¿Puedo renovarlo ahora?'
    r=service.responder(q)
    c=snapshot(service,r['session_id'])['contexto_canonico']
    assert r['intencion']=='dni_adulto_renovacion'
    assert c['edad']['valor']=='adulto'
    assert valor(c,'vigencia')==('hasta_60' if days<=60 else 'mas_60')
    assert {f['archivo'] for f in r['fuentes']}=={'dni_mayor_renovacion.txt'}
    assert {f['regla'] for f in r['fuentes']}=={'general'}
    assert 'primer DNI' not in r['respuesta']
    assert not prompts
    assert ('no corresponde renovar' in r['respuesta'])==(days==61)


@pytest.mark.parametrize('expression',['Quiero renovarlo','Necesito renovarlo','¿Puedo renovar mi DNI?',
    '¿Me corresponde renovarlo?', '¿Puedo renovarlo?'])
@pytest.mark.parametrize('days',[59,60,61])
def test_variantes_explicitas_conservan_operacion_y_vigencia(expression,days):
    s=clasificar({'pregunta':f'Soy adulto y mi DNI vence dentro de {days} días. {expression}'})
    assert s['intencion']=='dni_adulto_renovacion'
    assert s['operacion_dni']=='renovacion'
    assert valor(s['contexto_canonico'],'vigencia')==('hasta_60' if days<=60 else 'mas_60')
    assert extraer_evidencia(f'Mi DNI vence en {days} días. {expression}').solicitud

@pytest.mark.parametrize('days',[59,60,61])
@pytest.mark.parametrize('negative',['No quiero renovarlo','No necesito renovarlo','No corresponde renovarlo'])
def test_negaciones_no_solicitan_renovacion(days,negative,motor):
    service,_,_=motor
    r=service.responder(f'Soy mayor de edad y mi DNI vence dentro de {days} días. {negative}.')
    c=snapshot(service,r['session_id'])['contexto_canonico']
    assert 'renovacion' in c['rechazadas']
    assert c['operacion']['valor']!='renovacion'
    assert not r['fuentes']


@pytest.mark.parametrize('negative',['No quiero renovarlo','No necesito renovarlo','No corresponde renovarlo'])
def test_vencimiento_no_anula_negacion(negative,motor):
    service,_,_=motor
    r=service.responder(f'Soy adulto y mi DNI está vencido. {negative}.')
    assert not r['fuentes']
    assert 'renovacion' in snapshot(service,r['session_id'])['contexto_canonico']['rechazadas']


def test_repregunta_pronominal_y_rechazo_persistente(motor):
    service,_,_=motor
    first=service.responder('Soy adulto y mi DNI vence dentro de 59 días. ¿Puedo renovarlo ahora?')
    sid,token=first['session_id'],first['session_token']
    r=service.responder('¿Cuánto cuesta?',sid,token)
    assert r['intencion']=='dni_adulto_renovacion' and '€7' in r['respuesta']
    service.responder('No quiero renovarlo',sid,token)
    r=service.responder('Mi DNI vence dentro de 59 días',sid,token)
    assert not r['fuentes'] and 'renovacion' in snapshot(service,sid)['contexto_canonico']['rechazadas']
    r=service.responder('Ahora sí, quiero renovarlo',sid,token)
    assert r['intencion']=='dni_adulto_renovacion' and r['fuentes']
    assert 'renovacion' not in snapshot(service,sid)['contexto_canonico']['rechazadas']


def test_pronombre_en_aclaracion_no_pierde_operacion(motor):
    service,_,_=motor
    first=service.responder('Soy mayor de edad y mi DNI vence dentro de 60 días.')
    r=service.responder('¿Me corresponde renovarlo?',first['session_id'],first['session_token'])
    assert r['intencion']=='dni_adulto_renovacion'
    assert valor(snapshot(service,r['session_id'])['contexto_canonico'],'vigencia')=='hasta_60'


def test_reevaluacion_amarillo_conserva_solicitud_pronominal():
    evidence=extraer_evidencia('Soy adulto, tengo DNI amarillo y quiero renovarlo')
    assert evidence.operacion=='renovacion' and evidence.solicitud
    assert not evidence.observacion


@pytest.mark.parametrize('question',['Quiero renovarlo','Mi pasaporte vence dentro de 59 días. Quiero renovarlo'])
def test_pronombre_sin_referente_dni_no_recupera(question,motor):
    service,_,_=motor
    r=service.responder(question)
    assert not r['fuentes'] and r['intencion']!='dni_adulto_renovacion'


def test_cambio_titular_y_aislamiento_no_heredan_adulto(motor):
    service,_,_=motor
    first=service.responder('Soy adulto y mi DNI vence dentro de 61 días. Quiero renovarlo.')
    r=service.responder('Ahora quiero renovar el DNI de mi hijo menor',first['session_id'],first['session_token'])
    assert r['intencion']=='dni_menor_renovacion'
    assert {f['archivo'] for f in r['fuentes']}=={'dni_menor_renovacion.txt'}
    new=service.responder('¿Puedo renovarlo ahora?')
    assert new['session_id']!=first['session_id'] and not new['fuentes']
