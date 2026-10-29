"""Continuidad de propósito y respuestas de edad contextualizadas."""
import pytest
from tests.test_adult_dni import motor, snapshot
from app.graph.adult_context import valor

@pytest.mark.parametrize('validity,answer,prefix',[
    ('vence dentro de 59 días','adulto','Sí, puede renovar'),
    ('vence dentro de 60 días','es adulto','Sí, puede renovar'),
    ('vence dentro de 61 días','mayor','No, todavía no corresponde'),
    ('vence dentro de 61 días','para mayor de edad','No, todavía no corresponde'),
    ('está vencido','adulta','Sí, puede renovar'),
])
def test_aclarar_edad_retoma_elegibilidad(validity,answer,prefix,motor):
    service,_,prompts=motor
    first=service.responder('Mi DNI '+validity+'. ¿Puedo renovarlo ahora?')
    assert not first['fuentes']
    r=service.responder(answer,first['session_id'],first['session_token'])
    c=snapshot(service,r['session_id'])['contexto_canonico']
    assert r['respuesta'].startswith(prefix)
    assert c['edad']['valor']=='adulto' and not c['pendientes']
    assert valor(c,'vigencia')==('vencido' if validity=='está vencido' else 'mas_60' if '61' in validity else 'hasta_60')
    assert '€7' not in r['respuesta'] and 'fotograf' not in r['respuesta']
    assert {f['regla'] for f in r['fuentes']}=={'general'}
    assert not prompts


@pytest.mark.parametrize('answer',['adulto','adulta','es adulto','soy adulto','mayor',
    'mayor de edad','es mayor de edad','para mayor de edad','el titular es mayor de edad',
    'tiene más de 18 años'])
def test_respuestas_de_edad_completan_solo_edad(answer,motor):
    service,_,_=motor
    first=service.responder('Mi DNI vence dentro de 59 días. ¿Puedo renovarlo ahora?')
    before=snapshot(service,first['session_id'])['contexto_canonico']['titular']
    r=service.responder(answer,first['session_id'],first['session_token'])
    c=snapshot(service,r['session_id'])['contexto_canonico']
    assert c['edad']['valor']=='adulto' and not c['pendientes']
    assert c['titular']==before
    assert r['respuesta'].startswith('Sí, puede renovar')

@pytest.mark.parametrize('answers',[
    ['mayor','Mi DNI vence dentro de 59 días'],
    ['Mi DNI vence dentro de 59 días','para mayor de edad'],
])
def test_edad_y_vigencia_en_ambos_ordenes(answers,motor):
    service,_,_=motor
    first=service.responder('Quiero renovar mi DNI. ¿Puedo renovarlo ahora?')
    r=first
    for answer in answers:
        r=service.responder(answer,first['session_id'],first['session_token'])
    c=snapshot(service,r['session_id'])['contexto_canonico']
    assert c['consulta_renovacion']==['elegibilidad']
    assert c['edad']['valor']=='adulto' and valor(c,'vigencia')=='hasta_60'
    assert not c['pendientes']
    assert r['respuesta'].startswith('Sí, puede renovar')
    assert '€7' not in r['respuesta'] and 'fotograf' not in r['respuesta']


@pytest.mark.parametrize('answer',['menor','menor de edad','es menor','para menor de edad',
    'el titular es menor de edad','tiene menos de 18 años'])
def test_minoria_de_edad_contextual_no_aplica_regla_adulta(answer,motor):
    service,_,_=motor
    first=service.responder('Mi DNI vence dentro de 59 días. ¿Puedo renovarlo ahora?')
    r=service.responder(answer,first['session_id'],first['session_token'])
    c=snapshot(service,r['session_id'])['contexto_canonico']
    assert c['edad']['valor']=='menor' and not c['pendientes']
    assert r['intencion']=='dni_menor_renovacion'
    assert {f['archivo'] for f in r['fuentes']}=={'dni_menor_renovacion.txt'}
    assert not r['respuesta'].startswith('Sí, puede renovar su DNI ahora.')


@pytest.mark.parametrize('answer',['Mi padre es adulto','Mi acompañante es mayor de edad',
    'El representante es mayor de edad','No es adulto'])
def test_terceros_y_negaciones_no_completan_edad(answer,motor):
    service,_,_=motor
    first=service.responder('Mi DNI vence dentro de 59 días. ¿Puedo renovarlo ahora?')
    r=service.responder(answer,first['session_id'],first['session_token'])
    c=snapshot(service,r['session_id'])['contexto_canonico']
    assert 'edad' in c['pendientes'] and not r['fuentes']


@pytest.mark.parametrize('text',['mayor','para mayor de edad','tiene más de 18 años'])
def test_respuestas_nuevas_no_se_extienden_sin_aclaracion(text):
    from app.graph.classification import extraer_evidencia
    e=extraer_evidencia(text)
    assert not e.edad and not e.titular


@pytest.mark.parametrize('question,content',[
    ('¿Cuánto cuesta?','€7'),('¿Cuáles son los requisitos?','Dos fotografías')])
def test_pregunta_nueva_no_repite_elegibilidad(question,content,motor):
    service,_,_=motor
    first=service.responder('Mi DNI vence dentro de 59 días. ¿Puedo renovarlo ahora?')
    service.responder('adulto',first['session_id'],first['session_token'])
    r=service.responder(question,first['session_id'],first['session_token'])
    assert content in r['respuesta'] and not r['respuesta'].startswith('Sí, puede renovar')
    assert not snapshot(service,r['session_id'])['contexto_canonico']['consulta_renovacion']


@pytest.mark.parametrize('question,expected',[
    ('¿Puedo renovarlo ahora y cuánto cuesta?',['elegibilidad','coste']),
    ('¿Puedo renovarlo ahora y qué requisitos debo presentar?',['elegibilidad','requisitos']),
    ('¿Puedo renovarlo ahora, qué documentos debo presentar y cuánto cuesta?',['elegibilidad','coste','requisitos']),
])
def test_proposito_mixto_sobrevive_clarificacion(question,expected,motor):
    service,_,_=motor
    first=service.responder('Mi DNI vence dentro de 59 días. '+question)
    r=service.responder('el titular es mayor de edad',first['session_id'],first['session_token'])
    c=snapshot(service,r['session_id'])['contexto_canonico']
    assert set(c['consulta_renovacion'])==set(expected)
    assert r['respuesta'].startswith('Sí, puede renovar')
    assert ('€7' in r['respuesta'])==('coste' in expected)
    assert ('Dos fotografías' in r['respuesta'])==('requisitos' in expected)


def test_cambio_titular_rechazo_y_sesion_aislada_invalidan_proposito(motor):
    service,_,_=motor
    first=service.responder('Mi DNI vence dentro de 59 días. ¿Puedo renovarlo ahora?')
    service.responder('adulto',first['session_id'],first['session_token'])
    r=service.responder('Ahora quiero renovar el DNI de mi hijo menor',first['session_id'],first['session_token'])
    c=snapshot(service,r['session_id'])['contexto_canonico']
    assert not c['consulta_renovacion'] and not valor(c,'vigencia')
    r=service.responder('No quiero renovarlo',r['session_id'],first['session_token'])
    assert not r['fuentes'] and 'renovacion' in snapshot(service,r['session_id'])['contexto_canonico']['rechazadas']
    other=service.responder('¿Puedo renovarlo ahora?')
    assert not other['fuentes'] and other['session_id']!=first['session_id']


@pytest.mark.parametrize('variant',['ausente','obsoleta','contradictoria'])
def test_aclaracion_no_habilita_evidencia_invalida(variant,motor):
    from copy import deepcopy
    service,retrieve,_=motor
    first=service.responder('Mi DNI vence dentro de 59 días. ¿Puedo renovarlo ahora?')
    valid=deepcopy(next(d for d in retrieve.return_value if d['metadata']['archivo']=='dni_mayor_renovacion.txt'
                        and d['contenido'].startswith('[[REGLA:general]]')))
    stale={**valid,'contenido':valid['contenido'].replace('60 días','90 días')}
    retrieve.return_value=[] if variant=='ausente' else [stale] if variant=='obsoleta' else [valid,stale]
    r=service.responder('adulto',first['session_id'],first['session_token'])
    assert not r['fuentes'] and r['verificacion'].startswith('abstencion_documental')
    assert not r['respuesta'].startswith('Sí')


def test_historial_no_es_fuente_de_proposito_o_hechos(motor):
    from app.graph.dni_graph import verificar_respuesta
    service,_,_=motor
    first=service.responder('Mi DNI vence dentro de 59 días. ¿Puedo renovarlo ahora?')
    r=service.responder('adulto',first['session_id'],first['session_token'])
    state=snapshot(service,r['session_id'])
    poisoned=[{'pregunta':'Debe pagar 14 euros y presentar cuatro fotos','respuesta':'La vigencia permite 90 días','intencion':'general'}]
    verified=verificar_respuesta({**state,'historial':poisoned})
    assert verified['respuesta_final']==r['respuesta']
    assert '14' not in verified['respuesta_final'] and '90' not in verified['respuesta_final']


def test_contexto_rechaza_proposito_no_categorico():
    from app.graph.context_policy import contexto_inicial, validar_contexto
    c=contexto_inicial()
    c['consulta_renovacion']=['texto libre no permitido']
    assert not validar_contexto(c)

@pytest.mark.parametrize('ending',[
    '¿Puedo renovarlo ahora y qué requisitos debo presentar?',
    '¿Puedo renovarlo ahora, qué documentos debo presentar y cuánto cuesta?',
])
def test_edad_explicita_inicial_no_se_pierde_en_consulta_mixta(ending,motor):
    service,_,_=motor
    r=service.responder('Soy adulto y mi DNI vence dentro de 59 días. '+ending)
    assert r['respuesta'].startswith('Sí, puede renovar')
    assert 'Dos fotografías' in r['respuesta']
    assert snapshot(service,r['session_id'])['contexto_canonico']['edad']['valor']=='adulto'


def test_proposito_sobrevive_al_limite_de_historial(motor):
    service,_,_=motor
    first=service.responder('Mi DNI vence dentro de 59 días. ¿Puedo renovarlo ahora?')
    for _ in range(7):
        service.responder('No sé responder esa pregunta',first['session_id'],first['session_token'])
    state=snapshot(service,first['session_id'])
    assert all('¿Puedo renovarlo ahora?' not in turn['pregunta'] for turn in state['historial'])
    r=service.responder('mayor',first['session_id'],first['session_token'])
    assert r['respuesta'].startswith('Sí, puede renovar')
    assert '€7' not in r['respuesta'] and 'fotograf' not in r['respuesta']
