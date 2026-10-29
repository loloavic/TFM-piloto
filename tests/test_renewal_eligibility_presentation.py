"""Decisión al principio, sin modificar elegibilidad ni recuperación."""
import pytest
from tests.test_adult_dni import motor, snapshot

@pytest.mark.parametrize('days,initial',[(59,'Sí, puede renovar su DNI ahora.'),
    (60,'Sí, puede renovar su DNI ahora.'),(61,'No, todavía no corresponde renovar su DNI.')])
def test_decision_directa_de_gradio(days,initial,motor):
    service,_,prompts=motor
    r=service.responder(f'Soy mayor de edad y mi DNI vence dentro de {days} días. ¿Puedo renovarlo ahora?')
    assert r['respuesta'].startswith(initial)
    assert {f['regla'] for f in r['fuentes']}=={'general'}
    assert not prompts
    if days<=60:
        assert '€7' not in r['respuesta'] and 'Dos fotografías' not in r['respuesta']


def test_vigencia_desconocida_pide_solo_aclaracion(motor):
    service,_,_=motor
    r=service.responder('Soy adulto y quiero renovar mi DNI. ¿Puedo renovarlo ahora?')
    assert r['respuesta'].startswith('¿') and '60 días' in r['respuesta']
    assert '€7' not in r['respuesta'] and 'fotograf' not in r['respuesta']

@pytest.mark.parametrize('expression',['¿Me corresponde renovar mi DNI?', '¿Ya puedo renovar mi documento?',
    '¿Puedo renovarlo ahora?'])
@pytest.mark.parametrize('validity',['está vencido','vence dentro de 59 días','vence dentro de 60 días'])
def test_equivalentes_y_vencido_responden_afirmacion(expression,validity,motor):
    service,_,_=motor
    r=service.responder('Soy adulto y mi DNI '+validity+'. '+expression)
    assert r['respuesta'].startswith('Sí, puede renovar su DNI ahora.')
    assert 'fecha de vencimiento' not in r['respuesta']
    assert '€7' not in r['respuesta']
    assert 'fotograf' not in r['respuesta']


@pytest.mark.parametrize('question,initial,content',[
    ('¿Cuáles son los requisitos para renovarlo?','**Documentación','Dos fotografías'),
    ('¿Cuánto cuesta renovar el DNI?','**Tasa','€7'),
    ('¿Puedo renovar mi DNI ahora y qué requisitos debo presentar?','Sí, puede renovar','Dos fotografías'),
    ('¿Puedo renovarlo ahora y cuánto cuesta?','Sí, puede renovar','€7'),
])
def test_respuesta_centrada_en_lo_pedido(question,initial,content,motor):
    service,_,_=motor
    r=service.responder('Soy adulto y mi DNI vence dentro de 59 días. '+question)
    assert r['respuesta'].startswith(initial) and content in r['respuesta']
    if 'cuánto cuesta' in question.lower(): assert 'fotograf' not in r['respuesta']
    if 'requisitos' in question.lower():
        for fact in ['35x43 mm','fondo blanco','sin lentes','actual y distinta']:
            assert fact in r['respuesta']
        assert 'https://bookeo.com/cturin?' in r['respuesta']


@pytest.mark.parametrize('first_question', ['¿Puedo renovarlo ahora?', '¿Puedo renovarlo ahora y cuánto cuesta?'])
def test_aclaracion_continua_pregunta_de_elegibilidad(first_question,motor):
    service,_,_=motor
    first=service.responder('Soy adulto y quiero renovar mi DNI. '+first_question)
    r=service.responder('Mi DNI vence dentro de 60 días',first['session_id'],first['session_token'])
    assert r['respuesta'].startswith('Sí, puede renovar')
    assert ('€7' in r['respuesta'])==('cuánto cuesta' in first_question)
    assert 'fotograf' not in r['respuesta']
    r=service.responder('¿Cuánto cuesta?',r['session_id'],first['session_token'])
    assert r['respuesta'].startswith('**Tasa')
    assert 'Sí, puede renovar' not in r['respuesta']


@pytest.mark.parametrize('variant',['ausente','obsoleta','contradictoria','no_autorizada'])
def test_sin_evidencia_integra_no_hay_afirmacion(variant,motor):
    from copy import deepcopy
    service,retrieve,_=motor
    current=deepcopy(next(d for d in retrieve.return_value if d['metadata']['archivo']=='dni_mayor_renovacion.txt'
                        and d['contenido'].startswith('[[REGLA:general]]')))
    stale={**current,'contenido':current['contenido'].replace('60 días','90 días')}
    if variant=='ausente': retrieve.return_value=[]
    elif variant=='obsoleta': retrieve.return_value=[stale]
    elif variant=='contradictoria': retrieve.return_value=[current,stale]
    else:
        current['metadata']['archivo']='dni_menor_renovacion.txt';retrieve.return_value=[current]
    r=service.responder('Soy adulto y mi DNI vence dentro de 59 días. ¿Puedo renovarlo ahora?')
    assert not r['respuesta'].startswith('Sí')
    assert not r['fuentes'] and r['verificacion'].startswith('abstencion_documental')


def test_negacion_y_cambio_titular_no_producen_si_heredado(motor):
    service,_,_=motor
    first=service.responder('Soy adulto y mi DNI vence dentro de 59 días. ¿Puedo renovarlo ahora?')
    r=service.responder('No quiero renovarlo',first['session_id'],first['session_token'])
    assert not r['respuesta'].startswith('Sí') and not r['fuentes']
    r=service.responder('Ahora quiero renovar el DNI de mi hijo menor',first['session_id'],first['session_token'])
    assert r['intencion']=='dni_menor_renovacion'
    assert not r['respuesta'].startswith('Sí, puede renovar su DNI ahora.')


def test_verificador_compara_presentacion_final(motor):
    from app.graph.dni_graph import verificar_respuesta
    service,_,_=motor
    r=service.responder('Soy adulto y mi DNI vence dentro de 61 días. ¿Puedo renovarlo ahora?')
    verified=verificar_respuesta({**snapshot(service,r['session_id']),'respuesta_borrador':'Sí, puede renovar su DNI ahora.'})
    assert verified['respuesta_final']==r['respuesta']
    assert verified['respuesta_final'].startswith('No, todavía no corresponde')
    assert verified['verificacion'].startswith('observada:')


def test_elegibilidad_y_requisitos_pronominales_con_titular_activo(motor):
    service,_,_=motor
    first=service.responder('Soy adulto y quiero renovar mi DNI. Vence en 59 días.')
    r=service.responder('¿Puedo renovarlo ahora y qué requisitos debo presentar?',first['session_id'],first['session_token'])
    assert r['respuesta'].startswith('Sí, puede renovar')
    for fact in ['Dos fotografías','35x43 mm','fondo blanco','sin lentes']:
        assert fact in r['respuesta']
