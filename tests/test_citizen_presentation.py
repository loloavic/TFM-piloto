"""Claridad sin reformulación LLM de los controles documentales."""
import pytest
from tests.test_adult_dni import motor, snapshot, REPORTED_ADULT_QUERY
from tests.test_widow_answers import PENDING

TECHNICAL = ['.txt', '[[REGLA:', 'OBSERVACIÓN PENDIENTE', 'ficha PDF',
             'corpus', 'plazo común se registra', 'reglas verificables']

@pytest.mark.parametrize('question', [
    PENDING+' Mi esposo era italiano.', PENDING+' Mi esposo no era italiano.',
    REPORTED_ADULT_QUERY.replace('¿Qué requisitos debo presentar y cuánto cuesta?', '¿Qué documentos debo presentar?'),
])
def test_salida_controlada_sin_detalles_de_implementacion(question,motor):
    service,_,_=motor
    r=service.responder(question)
    for word in TECHNICAL: assert word not in r['respuesta']


def test_abstencion_integra_pero_comprensible(motor):
    service,retrieve,_=motor
    retrieve.return_value=[]
    r=service.responder('Soy adulto y quiero renovar mi DNI. ¿Cuánto demora?')
    assert not r['fuentes'] and r['verificacion'].startswith('abstencion_documental')
    assert 'Consulado' in r['respuesta']
    for word in TECHNICAL: assert word not in r['respuesta']

@pytest.mark.parametrize('question', [
    'Soy adulto y quiero renovar mi DNI. ¿Cuánto cuesta?',
    'Quiero renovar el DNI de mi hijo menor. ¿Qué documentos debo presentar?',
    'Quiero cambiar mi DNI amarillo a azul. ¿Qué documentos debo presentar?',
    'Soy adulto y quiero rectificar mi fecha de nacimiento en el DNI vigente. ¿Qué documentos debo presentar?',
])
def test_instrucciones_claras_sin_segunda_reformulacion(question,motor,monkeypatch):
    from app.graph import dni_graph
    service,_,_=motor
    calls=[]
    class Local:
        def generar_respuesta(self,prompt):
            calls.append(prompt)
            assert 'No menciones TXT, PDF, corpus' in prompt
            assert 'conserva todas las condiciones obligatorias' in prompt
            assert 'No añadas importes totales' in prompt
            return 'Consulte las condiciones de su trámite antes de acudir.'
    monkeypatch.setattr(dni_graph,'LLMService',Local)
    r=service.responder(question)
    assert len(calls)==(0 if 'renovar mi DNI' in question else 1) and r['fuentes']
    if 'renovar mi DNI' in question:
        assert '€7' in r['respuesta']
    state=snapshot(service,r['session_id'])
    assert r['respuesta']==state['respuesta_borrador']==state['historial'][-1]['respuesta']


def test_viudez_conserva_documentos_condiciones_y_enlace(motor):
    service,_,prompts=motor
    q=PENDING.replace('No quiero recuperar el apellido materno.','Quiero recuperar el apellido materno.')+' Mi esposo era italiano.'
    r=service.responder(q)
    text=r['respuesta']
    for fact in ['municipalidad italiana','Prefectura','sustituye','No necesita presentar una certificación consular',
                 'si está registrado en Perú','si está registrado en una oficina consular peruana',
                 'acta de nacimiento original','12 meses','apostilladas','35x43 mm','sin lentes',
                 'sin marco','fondo blanco','frente descubierta','cuello visible']:
        assert fact in text
    assert '<details>' in text and '</details>' in text
    assert 'https://bookeo.com/cturin?type=223Y6PNNP174468CBDCD&option_TYPE_OF_SERVICE=YJUTCFLT' in text
    assert text.index('**Defunción:**') < text.index('**Condiciones del trámite**')
    assert not prompts
    assert r['verificacion'] == 'ok'


@pytest.mark.parametrize('topic,expected', [
    ('¿Cuánto demora?',['3 a 4 meses','referencial','no significa']),
    ('¿Cómo consulto el estado de mi DNI?',['100 %','no constituye','https://serviciosportal.reniec.gob.pe/cetdnipi/inicio.htm']),
    ('¿Qué recomendaciones debo tener en cuenta?',['cita previa','vigentes','fotografías']),
])
def test_tema_conserva_hechos_y_evitar_requisitos_viudez(topic,expected,motor):
    service,_,_=motor
    first=service.responder(PENDING+' Mi esposo era italiano.')
    r=service.responder(topic,first['session_id'],first['session_token'])
    for fact in expected: assert fact in r['respuesta']
    assert 'plurilingüe' not in r['respuesta'] and '35x43' not in r['respuesta']
    assert snapshot(service,first['session_id'])['operacion_dni']=='rectificacion'


@pytest.mark.parametrize('question', ['¿Qué documentos debo presentar?','¿Cuánto cuesta?', '¿Qué fotografías necesito?'])
def test_control_final_rechaza_reformulacion_insegura(question,motor):
    from app.graph.dni_graph import verificar_respuesta
    service,_,_=motor
    first=service.responder(REPORTED_ADULT_QUERY)
    r=service.responder(question,first['session_id'],first['session_token'])
    state=snapshot(service,first['session_id'])
    bad='Debe pagar una tasa única de 14 euros para ambos trámites y presentar cuatro fotos.'
    checked=verificar_respuesta({**state,'respuesta_borrador':bad})
    assert checked['respuesta_final']==r['respuesta']
    assert checked['verificacion'].startswith('observada:')
    assert bad not in checked['historial'][-1]['respuesta']
    assert 'combinad' in checked['respuesta_final']


@pytest.mark.parametrize('variant',['ausente','obsoleta','contradictoria'])
def test_presentacion_no_oculta_integridad_fallida(variant,motor):
    from copy import deepcopy
    service,retrieve,prompts=motor
    valid=deepcopy(next(d for d in retrieve.return_value if d['metadata']['archivo']=='dni_mayor_renovacion.txt'
                        and d['contenido'].startswith('[[REGLA:plazo]]')))
    stale={**valid,'contenido':'[[REGLA:plazo]]El plazo es de 99 meses.[[FIN]]'}
    retrieve.return_value=[] if variant=='ausente' else [stale] if variant=='obsoleta' else [valid,stale]
    r=service.responder('Soy adulto y quiero renovar mi DNI. ¿Cuánto demora?')
    assert not r['fuentes'] and not prompts and '99 meses' not in r['respuesta']
    assert r['verificacion'].startswith('abstencion_documental')
    assert 'Consulado' in r['respuesta']


def test_incertidumbre_preserva_informacion_confirmada_y_auditoria(motor):
    service,_,_=motor
    first=service.responder(PENDING+' Mi esposo no era italiano.')
    state=snapshot(service,first['session_id'])
    assert 'OBSERVACIÓN PENDIENTE' in state['contexto']
    assert 'OBSERVACIÓN PENDIENTE' not in first['respuesta']
    assert first['verificacion'].startswith('abstencion_documental')
    assert 'no puedo confirmar' in first['respuesta'].lower()
    assert 'si está registrado en Perú' in first['respuesta']
    assert 'si está registrado en una oficina consular peruana' in first['respuesta']
    assert '35x43 mm' in first['respuesta']
    assert 'No necesita presentar una certificación consular' not in first['respuesta']
    assert 'acta plurilingüe' not in first['respuesta']


def test_gradio_y_api_conservan_detalles_documentales(motor,monkeypatch):
    from app import ui
    from app.main import app
    from fastapi.testclient import TestClient
    service,_,_=motor
    monkeypatch.setattr(ui,'rag',service)
    q=PENDING+' Mi esposo era italiano.'
    with TestClient(app) as client:
        result=client.post('/api/v1/consultas',json={'pregunta':q})
        assert result.status_code==200
        text=result.json()['respuesta']
        assert 'sin lentes' in text and '</details>' in text
        assert 'plurilingüe' in text
    result=ui.responder_consulta(q,[],ui.generar_session_id())
    assert 'sin lentes' in result[1][-1]['content']
    assert '<details>' in result[1][-1]['content']


def test_rechazo_final_de_obligacion_inventada_en_viudez_incierta(motor):
    from app.graph.dni_graph import verificar_respuesta
    service,_,_=motor
    r=service.responder(PENDING+' Mi esposo no era italiano.')
    state=snapshot(service,r['session_id'])
    bad='Presente obligatoriamente ambas actas de defunción y pague 14 euros.'
    verified=verificar_respuesta({**state,'respuesta_borrador':bad})
    assert verified['respuesta_final']==r['respuesta']
    assert verified['verificacion'].startswith('observada:')
    assert bad not in verified['historial'][-1]['respuesta']
