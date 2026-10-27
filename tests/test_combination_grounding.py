"""Proveedor hostil y verificación final: no hay OpenAI ni FAISS reales."""
import pytest
from tests.test_adult_dni import motor, snapshot, REPORTED_ADULT_QUERY

BAD_OUTPUTS = [
    'Se paga una tasa única de 7 euros por el trámite de rectificación/renovación.',
    'El importe total es 14 euros y se requieren cuatro fotografías.',
    'La renovación está exonerada: solo debe abonar 7 euros y presentar dos fotos para ambos trámites.',
    'No necesita apostilla ni acta original. Basta una fotocopia simple para ambos procedimientos.',
]


@pytest.fixture
def hostile(motor, monkeypatch):
    from app.graph import dni_graph
    service, retrieve, _ = motor
    calls=[]
    class Hostile:
        def generar_respuesta(self, prompt):
            calls.append(prompt)
            return BAD_OUTPUTS[0]
    monkeypatch.setattr(dni_graph,'LLMService',Hostile)
    return service,retrieve,calls


@pytest.mark.parametrize('question', [
    'Entiendo. ¿Y qué documentos debo presentar para rectificar mi fecha de nacimiento si mi DNI está vencido?',
    '¿Qué fotografías debo presentar?',
    '¿Cuáles son los requisitos?',
])
def test_proveedor_no_puede_decidir_condiciones_combinadas(question, hostile):
    service,_,calls=hostile
    first=service.responder(REPORTED_ADULT_QUERY)
    r=service.responder(question,first['session_id'],first['session_token'])
    assert not calls  # La combinación restringida no se delega al modelo.
    assert BAD_OUTPUTS[0] not in r['respuesta']
    assert 'combinad' in r['respuesta'].lower()
    if 'documentos' in question or 'requisitos' in question:
        assert 'partida de nacimiento original apostillada' in r['respuesta']


@pytest.mark.parametrize('followup', [None, '¿Qué documentos debo presentar?', '¿Qué fotografías necesito?'])
@pytest.mark.parametrize('bad', BAD_OUTPUTS)
def test_verificador_final_rechaza_borrador_inyectado(bad, followup, hostile):
    from app.graph import dni_graph
    service,_,_=hostile
    first=service.responder(REPORTED_ADULT_QUERY)
    if followup:
        service.responder(followup,first['session_id'],first['session_token'])
    s=snapshot(service,first['session_id'])
    r=dni_graph.verificar_respuesta({**s,'respuesta_borrador':bad})
    assert r['respuesta_final'] != bad
    assert r['respuesta_borrador'] == r['respuesta_final']
    assert r['verificacion'].startswith('observada:')
    assert r['historial'][-1]['respuesta'] == r['respuesta_final']
    assert bad not in r['historial'][-1]['respuesta']


def test_ciclo_de_temas_conserva_limites_y_fuentes(hostile):
    service,_,calls=hostile
    first=service.responder(REPORTED_ADULT_QUERY)
    sid,token=first['session_id'],first['session_token']
    for question in ['¿Qué requisitos debo presentar?', '¿Cuánto cuesta?',
                     '¿Y las fotografías?', '¿Dónde solicito la cita?',
                     '¿Cuánto demora?', '¿Qué documentos debo presentar?']:
        r=service.responder(question,sid,token)
        assert {f['archivo'] for f in r['fuentes']} == {'dni_mayor_rectificacion.txt','dni_mayor_renovacion.txt'}
        assert r['verificacion'] == 'ok'  # Plantilla de alcance cerrado, no borrador LLM.
        assert ('3 a 4 meses' in r['respuesta'] if 'demora' in question else 'combinad' in r['respuesta'])
        assert r['session_id'] == sid and r['session_token'] == token
        assert not calls
    assert snapshot(service,sid)['operacion_dni'] == 'rectificacion'


@pytest.mark.parametrize('question,file', [
    ('Soy adulto y quiero renovar mi DNI', 'dni_mayor_renovacion.txt'),
    ('Soy adulto y quiero rectificar mi fecha de nacimiento en el DNI vigente','dni_mayor_rectificacion.txt'),
    ('Quiero renovar el DNI de mi hijo menor','dni_menor_renovacion.txt'),
    ('Mi hijo menor necesita su primer DNI','dni_menor_primera_vez.txt'),
    ('Quiero cambiar mi DNI amarillo a azul','dni_amarillo_a_azul_primera_vez.txt'),
    ('Quiero consultar el estado del trámite de mi DNI','dni_consulta_estado.txt'),
])
def test_procedimientos_individuales_siguen_generando(question,file,motor,monkeypatch):
    from app.graph import dni_graph
    service,_,_=motor
    calls=[]
    class Individual:
        def generar_respuesta(self,prompt):
            calls.append(prompt)
            return 'La tasa individual de este procedimiento adulto es €7.' if file.startswith('dni_mayor') else 'Información individual según su ficha.'
    monkeypatch.setattr(dni_graph,'LLMService',Individual)
    first=service.responder(question)
    assert {f['archivo'] for f in first['fuentes']} == {file}
    assert calls and first['verificacion'] == 'ok'
    if file.startswith('dni_mayor'):
        r=service.responder('¿Cuánto cuesta?',first['session_id'],first['session_token'])
        assert '€7' in r['respuesta'] and len(calls) == 2


def test_combinacion_civil_no_autorizada_tampoco_acepta_borrador(hostile):
    from app.graph import dni_graph
    service,_,calls=hostile
    r=service.responder('Soy adulto y quiero renovar mi DNI y cambiar mi estado civil')
    assert not r['fuentes'] and not calls
    assert 'no está confirmada' in r['respuesta']
    s=snapshot(service,r['session_id'])
    verified=dni_graph.verificar_respuesta({**s,'respuesta_borrador':BAD_OUTPUTS[0]})
    assert verified['verificacion'].startswith('observada:')
    assert 'no está confirmada' in verified['respuesta_final']


def test_fuente_faltante_no_autoriza_ningun_total(hostile):
    from app.graph import dni_graph
    service,retrieve,calls=hostile
    retrieve.return_value=[d for d in retrieve.return_value if d['metadata']['archivo'] != 'dni_mayor_renovacion.txt']
    r=service.responder(REPORTED_ADULT_QUERY)
    assert not r['fuentes'] and not calls
    assert 'No cuento con información documental suficiente' in r['respuesta']
    s=snapshot(service,r['session_id'])
    verified=dni_graph.verificar_respuesta({**s,'respuesta_borrador':BAD_OUTPUTS[1]})
    assert verified['verificacion'].startswith('observada:')
    assert verified['respuesta_final'] == r['respuesta']
