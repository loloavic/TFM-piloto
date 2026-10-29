import pytest
from tests.test_adult_dni import motor, snapshot

EMAIL='informes@conperturin.org'
MINOR='Mi hija de 16 años necesita actualizar su estado civil en el DNI. ¿Qué documentos debe presentar?'


def test_menor_derivado_recibe_contacto_sin_alterar_decision(motor):
    service,retrieve,prompts=motor
    r=service.responder(MINOR)
    assert EMAIL in r['respuesta']
    assert r['intencion']=='general' and not r['fuentes']
    assert r['verificacion']=='ok'
    assert not retrieve.called and not prompts
    c=snapshot(service,r['session_id'])['contexto_canonico']
    assert c['edad']['valor']=='menor' and c['operacion']['valor']=='rectificacion'

@pytest.mark.parametrize('text',[
 'Consulte con el Consulado antes de acudir.',
 'Confirme con el Consulado la cantidad de fotografías.',
 'Por favor, consulte los canales oficiales del consulado.',
 'La combinación requiere confirmación del Consulado.',
 'Puede comunicarse directamente con la oficina consular.',
 'Le recomiendo escribir al Consulado.',
 'Debe confirmar con el Consulado qué actas necesita.',
])
def test_derivaciones_explicitas_idempotentes(text):
    from app.graph.referral import incorporar_contacto
    result=incorporar_contacto(text)
    assert result.startswith(text)
    assert result.count(EMAIL)==2  # Una etiqueta y su destino mailto.
    assert incorporar_contacto(result)==result

@pytest.mark.parametrize('text',[
 'Consulte el sistema Bookeo para reservar su cita.',
 'Consulte el portal RENIEC; el 100 % no garantiza disponibilidad.',
 '¡Buenas noches! ¿En qué puedo ayudarle?',
 'No es necesario contactar con el Consulado.',
 'No necesita confirmar con el Consulado este punto.',
 'El Consulado tramita solicitudes de DNI.',
 'La tasa individual documentada es 7 €.',
])
def test_no_agrega_contacto_sin_derivacion(text):
    from app.graph.referral import incorporar_contacto
    assert incorporar_contacto(text)==text

@pytest.mark.parametrize('text',[
 'Consulte con el Consulado: informes@conperturin.org',
 'Escriba al Consulado: INFORMES@CONPERTURIN.ORG',
 '[informes@conperturin.org](mailto:informes@conperturin.org)',
])
def test_contacto_existente_no_se_duplica(text):
    from app.graph.referral import incorporar_contacto
    assert incorporar_contacto(text)==text

@pytest.mark.parametrize('failure',['ausente','contradictoria'])
def test_abstencion_y_verificacion_se_conservan(failure,motor,monkeypatch):
    from app.graph import dni_graph
    from app.graph.referral import incorporar_contacto
    service,retrieve,prompts=motor
    if failure=='ausente':
        retrieve.return_value=[]
    else:
        import copy
        docs=copy.deepcopy(retrieve.return_value)
        item=next(d for d in docs if d['metadata']['archivo']=='dni_mayor_renovacion.txt')
        item['contenido']=item['contenido'].replace('€7','€99')
        retrieve.return_value=docs
    q='Soy adulto y necesito renovar mi DNI'
    monkeypatch.setattr(dni_graph,'incorporar_contacto',lambda text:text)
    before=service.responder(q)
    before_state=snapshot(service,before['session_id'])
    monkeypatch.setattr(dni_graph,'incorporar_contacto',incorporar_contacto)
    after=service.responder(q)
    after_state=snapshot(service,after['session_id'])
    assert EMAIL not in before['respuesta'] and EMAIL in after['respuesta']
    assert after['verificacion']==before['verificacion']
    assert after['verificacion'].startswith('abstencion_documental')
    assert after['intencion']==before['intencion'] and after['fuentes']==before['fuentes']==[]
    assert before_state['contexto_canonico']==after_state['contexto_canonico']
    assert not prompts


def test_combinacion_no_confirmada_ofrece_contacto(motor):
    service,_,prompts=motor
    r=service.responder('Soy adulto y necesito renovar mi DNI y actualizar mi estado civil a divorciado')
    assert EMAIL in r['respuesta'] and 'no está confirmada' in r['respuesta']
    assert not prompts

@pytest.mark.parametrize('query',[
 'Buenas noches',
 'Soy adulto y necesito renovar mi DNI. ¿Cuánto cuesta?',
 'Soy adulto y necesito renovar mi DNI. ¿Dónde solicito cita?',
 'Soy adulto y necesito renovar mi DNI. ¿Cómo consulto el estado de mi DNI?',
])
def test_no_sustituye_cita_seguimiento_ni_social(query,motor):
    service,_,_=motor
    r=service.responder(query)
    assert EMAIL not in r['respuesta']
    if 'cita' in query:
        assert 'bookeo.com' in r['respuesta']
    if 'estado de mi DNI' in query:
        assert 'reniec.gob.pe' in r['respuesta']


def test_contacto_no_se_hereda_entre_turnos_o_sesiones(motor):
    service,_,_=motor
    r=service.responder(MINOR)
    sid,token=r['session_id'],r['session_token']
    assert EMAIL in r['respuesta']
    r=service.responder('Ahora quiero renovar mi DNI, soy adulto',sid,token)
    assert r['intencion']=='dni_adulto_renovacion'
    assert EMAIL not in r['respuesta']
    assert EMAIL not in service.responder('Hola')['respuesta']


def test_cita_con_derivacion_conserva_bookeo(motor):
    service,_,_=motor
    r=service.responder('Soy adulto y necesito actualizar mi DNI a divorciado')
    assert EMAIL in r['respuesta'] and 'bookeo.com' in r['respuesta']

@pytest.mark.parametrize('text',[
 'Confirme este punto con el Consulado antes de acudir.',
 'Le recomiendo confirmar los requisitos con la oficina consular.',
 'Puede contactar al Consulado.',
])
def test_derivacion_con_objeto_intermedio(text):
    from app.graph.referral import incorporar_contacto
    assert EMAIL in incorporar_contacto(text)


def test_derivacion_generada_explicita_preserva_observada(monkeypatch):
    from app.graph.dni_graph import verificar_respuesta
    from app.graph import dni_graph
    monkeypatch.setattr(dni_graph,'respuesta_controlada',lambda state:None)
    state={'pregunta':'Quiero contactar con el Consulado', 'intencion':'dni_consulta_estado',
           'respuesta_borrador':'Consulte con el Consulado indicando su número de DNI.',
           'fuentes':[], 'historial':[]}
    result=verificar_respuesta(state)
    assert EMAIL in result['respuesta_final']
    assert result['verificacion'].startswith('observada:')
    assert result['fuentes']==[]

@pytest.mark.parametrize('text',[
 'No contacte con el Consulado para reservar una cita.',
 'No le recomiendo contactar con el Consulado para este punto.',
])
def test_derivaciones_negadas_no_agregan(text):
    from app.graph.referral import incorporar_contacto
    assert incorporar_contacto(text)==text
