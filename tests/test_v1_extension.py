"""V1: documentos reales del corpus y proveedores simulados, sin OpenAI."""
import re
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.graph.classification import clasificar
from app.graph.context_policy import CAMBIO_AZUL, DOCUMENTOS_POR_INTENCION

BLUE = 'dni_amarillo_a_azul_primera_vez'
BLUE_URL = 'https://bookeo.com/cturin?type=223Y6PNNP174468CBDCD&option_TYPE_OF_SERVICE=YJUTCFLT'
MINOR_URL = 'https://bookeo.com/cturin?type=223Y6PNNP174468CBDCD&option_TYPE_OF_SERVICE=YMRKCTKN'


def turn(s, q):
    return clasificar({**s, 'pregunta': q})


@pytest.fixture
def motor(monkeypatch, entorno_aislado):
    from app.graph import dni_graph
    docs = [{'contenido': p.read_text(encoding='utf-8'), 'score': 0.1,
             'metadata': {'archivo': p.name, 'chunk': 0}}
            for p in sorted(Path('data/raw').glob('*.txt'))]
    retrieve = Mock(return_value=docs)
    prompts = []
    class GroundedStub:
        def generar_respuesta(self, prompt):
            # Prueba del flujo, no una validación de comprensión de un LLM.
            prompts.append(prompt)
            context = prompt.split('CONTEXTO DOCUMENTAL:\n', 1)[1].split('PREGUNTA ACTUAL DEL CIUDADANO:', 1)[0]
            question = prompt.split('PREGUNTA ACTUAL DEL CIUDADANO:', 1)[1].lower()
            if 'cuesta' in question or 'coste' in question:
                if '€7' in context:
                    return 'La tasa es €7 para el supuesto documentado de cumplir 17 años con DNI amarillo.'
                assert '5.00 euros' in context or '€5' in context
                return 'La tasa es €5.'
            if 'cita' in question:
                return next(url for url in re.findall(r'https?://\S+', context) if 'bookeo' in url)
            if 'foto' in question:
                return context.split('2. Dos fotografías', 1)[1].split('CITA PREVIA', 1)[0] if '2. Dos fotografías' in context else 'Fotografías según la fuente.'
            if 'demora' in question:
                return 'El plazo referencial documentado es de 3 a 4 meses.'
            return 'Respuesta simulada basada únicamente en el contexto seleccionado.'
    monkeypatch.setattr(dni_graph, 'recuperar_contexto', retrieve)
    monkeypatch.setattr(dni_graph, 'LLMService', GroundedStub)
    return entorno_aislado, retrieve, prompts


def state(service, sid):
    return service.grafo.get_state({'configurable': {'thread_id': sid}}).values


@pytest.mark.parametrize('question', [
    'Mi hijo cumple 17 años y necesita cambiar su DNI amarillo por el azul',
    'Quiero cambiar mi DNI amarillo a azul',
    '¿Qué requisitos necesito para sacar el DNI azul si ya tengo el amarillo?',
    'Mi hija tiene 17 años y necesita pasar del DNI amarillo al azul',
])
def test_identificacion_inequivoca_amarillo_azul(question, motor):
    service, _, prompts = motor
    result = service.responder(question)
    assert result['intencion'] == BLUE
    s = state(service, result['session_id'])
    assert s['contexto_canonico']['operacion']['valor'] == CAMBIO_AZUL
    assert not s['requiere_aclaracion']
    assert {f['archivo'] for f in result['fuentes']} == {BLUE + '.txt'}
    context = prompts[-1].split('CONTEXTO DOCUMENTAL:\n', 1)[1].split('PREGUNTA ACTUAL DEL CIUDADANO:', 1)[0]
    assert '€7' in context and BLUE_URL in context
    assert '€5' not in context and MINOR_URL not in context
    assert 'Acta de nacimiento' not in context


@pytest.mark.parametrize('question', ['DNI azul', '¿Cuánto cuesta el DNI azul por primera vez?', 'Quiero el primer DNI'])
def test_ambiguas_no_recuperan_procedimiento_al_azar(question, motor):
    service, retrieve, prompts = motor
    result = service.responder(question)
    assert result['intencion'] == 'general' and not result['fuentes']
    assert state(service, result['session_id'])['requiere_aclaracion']
    assert not retrieve.called and not prompts


def test_edad_sola_no_activa_cambio_de_color():
    s = turn({}, 'Mi hijo cumple 17 años y necesita tramitar el DNI')
    assert s['requiere_aclaracion'] and s['intencion'] != BLUE


def test_repreguntas_tarifa_fotos_plazo_y_url_exacta(motor):
    service, _, prompts = motor
    first = service.responder('Mi hijo cumple 17 años y necesita cambiar su DNI amarillo por el azul')
    sid, token = first['session_id'], first['session_token']
    for question, expected in [
        ('¿Cuánto cuesta el DNI azul por primera vez?', '€7'),
        ('¿Y las fotografías?', '35 x 43 mm'),
        ('¿Dónde solicito la cita?', BLUE_URL),
        ('¿Cuánto demora?', '3 a 4 meses'),
    ]:
        result = service.responder(question, sid, token)
        assert result['intencion'] == BLUE and expected in result['respuesta']
        assert {f['archivo'] for f in result['fuentes']} == {BLUE + '.txt'}
        assert result['session_token'] == token and result['session_id'] == sid
    assert all('No los\n  cambies' in p for p in prompts)


@pytest.mark.parametrize('intent,question', [
    ('dni_menor_primera_vez', 'Mi hijo menor necesita su primer DNI'),
    ('dni_menor_renovacion', 'Necesito renovar el DNI de mi hijo menor'),
])
def test_filtro_exacto_conserva_cinco_euros_y_cita_anterior(intent, question, motor):
    service, _, prompts = motor
    first = service.responder(question)
    sid, token = first['session_id'], first['session_token']
    result = service.responder('¿Cuánto cuesta?', sid, token)
    assert result['respuesta'] == 'La tasa es €5.'
    assert {f['archivo'] for f in result['fuentes']} == {DOCUMENTOS_POR_INTENCION[intent]}
    result = service.responder('¿Dónde solicito la cita?', sid, token)
    assert result['respuesta'] == MINOR_URL
    context = prompts[-1].split('CONTEXTO DOCUMENTAL:\n', 1)[1].split('PREGUNTA ACTUAL DEL CIUDADANO:', 1)[0]
    assert BLUE_URL not in context and '€7' not in context


def test_documentos_ajenos_no_sustituyen_fuente_ausente(motor):
    service, retrieve, prompts = motor
    retrieve.return_value = [d for d in retrieve.return_value if d['metadata']['archivo'] != BLUE + '.txt']
    result = service.responder('Quiero cambiar mi DNI amarillo a azul')
    assert not result['fuentes'] and not prompts
    assert 'No cuento con información documental suficiente' in result['respuesta']
    assert state(service, result['session_id'])['estado_documental'] == 'sin_evidencia'


def test_negacion_y_rectificacion_no_rehabilitan_mediante_color():
    s = turn({}, 'Mi hijo tiene 17 años y necesita pasar de DNI amarillo a azul')
    s = turn(s, 'No quiero cambiar el DNI amarillo a azul')
    assert CAMBIO_AZUL in s['contexto_canonico']['rechazadas'] and s['requiere_aclaracion']
    s = turn(s, '¿Cuánto cuesta el DNI azul por primera vez?')
    s = turn(s, 'Ya tengo el amarillo')
    assert s['requiere_aclaracion'] and CAMBIO_AZUL in s['contexto_canonico']['rechazadas']
    s = turn(s, 'Quiero cambiar mi DNI amarillo a azul')
    assert s['intencion'] == BLUE and not s['requiere_aclaracion']


def test_cambio_de_tramite_y_nueva_sesion(motor):
    service, _, _ = motor
    first = service.responder('Mi hijo tiene 17 años y necesita cambiar DNI amarillo a azul')
    sid, token = first['session_id'], first['session_token']
    changed = service.responder('Ahora necesito el primer DNI de mi otro hijo menor', sid, token)
    assert changed['intencion'] == 'dni_menor_primera_vez'
    assert {f['archivo'] for f in changed['fuentes']} == {'dni_menor_primera_vez.txt'}
    fresh = service.responder('¿Cuánto cuesta el DNI azul por primera vez?')
    assert fresh['intencion'] == 'general' and not fresh['fuentes']
    service.sessions.delete(sid, token)
    assert not list(service.grafo.checkpointer.list({'configurable': {'thread_id': sid}}))
    restarted = service.responder('¿Y la cita?')
    assert restarted['intencion'] == 'general'


@pytest.mark.parametrize('partial', ['Debo actualizar el domicilio',
    'Necesito actualizar DNI de mi hijo menor por cambio de domicilio', 'Quiero cambiar el domicilio'])
def test_nueva_informacion_domicilio_no_equivale_a_renovacion(motor, partial):
    service, retrieve, prompts = motor
    first = service.responder('Buenos días, necesito tramitar el DNI de mi hijo menor')
    sid, token = first['session_id'], first['session_token']
    second = service.responder(partial, sid, token)
    assert 'Entiendo que necesita actualizar el domicilio' in second['respuesta']
    assert '¿Desea orientación sobre una renovación o sobre el primer DNI?' in second['respuesta']
    assert second['respuesta'] != first['respuesta']
    assert second['verificacion'] == 'ok'
    assert not state(service, sid)['operacion_dni'] and state(service, sid)['requiere_aclaracion']
    assert not retrieve.called and not prompts


@pytest.mark.parametrize('question,phrase', [
    ('El enlace de citas no funciona', 'no puede abrir el enlace'),
    ('La página de reservas da error', 'no puedo determinar si se debe a falta de citas'),
    ('No aparecen citas disponibles', 'no puedo confirmar cuándo'),
    ('Necesito una cita lo antes posible', 'no puedo garantizar una cita anticipada'),
])
def test_incidencias_contextuales_sin_causas_inventadas(question, phrase, motor):
    service, _, prompts = motor
    first = service.responder('Necesito renovar el DNI de mi hijo menor')
    sid, token = first['session_id'], first['session_token']
    before = len(prompts)
    result = service.responder(question, sid, token)
    assert phrase in result['respuesta'].lower()
    assert '15' not in result['respuesta'] and 'https://' not in result['respuesta']
    assert result['intencion'] == 'dni_menor_renovacion'
    assert len(prompts) == before
    assert state(service, sid)['operacion_dni'] == 'renovacion'


def test_domicilio_no_documentado_en_tramite_confirmado_se_abstiene(motor):
    service, _, prompts = motor
    first = service.responder('Necesito renovar el DNI de mi hijo menor')
    result = service.responder('Quiero actualizar el domicilio', first['session_id'], first['session_token'])
    assert 'no especifica' in result['respuesta'] and 'no puedo confirmar' in result['respuesta']
    assert len(prompts) == 1


def test_url_aprobada_conservada_y_fuente_sin_modificar():
    from app.core.privacy import minimizar_texto
    text = Path('data/raw/' + BLUE + '.txt').read_text(encoding='utf-8')
    assert BLUE_URL in text and '€7' in text and '35 x 43 mm' in text
    assert minimizar_texto(BLUE_URL, permitir_oficiales=True) == BLUE_URL


def test_negacion_de_primera_inscripcion_se_conserva_al_mencionar_azul():
    s = turn({}, 'No es su primer DNI; quiero cambiar mi DNI amarillo a azul')
    assert s['intencion'] == BLUE
    assert 'primera_vez' in s['contexto_canonico']['rechazadas']


def test_tenencia_de_dni_amarillo_no_sustituye_operacion_rechazada(motor):
    service, retrieve, prompts = motor
    first = service.responder('Mi hijo cumple 17 años y necesita cambiar DNI amarillo a azul')
    sid, token = first['session_id'], first['session_token']
    service.responder('No quiero cambiar el DNI amarillo a azul', sid, token)
    before = retrieve.call_count, len(prompts)
    result = service.responder('Ya tiene el DNI amarillo', sid, token)
    assert result['intencion'] == 'general' and not result['fuentes']
    assert (retrieve.call_count, len(prompts)) == before
    assert CAMBIO_AZUL in state(service, sid)['contexto_canonico']['rechazadas']


def test_dni_amarillo_no_es_primera_inscripcion_ni_cambio_automatico():
    s = turn({}, 'Mi hijo de 17 años necesita su primer DNI')
    s = turn(s, 'Ya tiene el DNI amarillo')
    assert s['requiere_aclaracion'] and s['intencion'] == 'general'
    assert s['motivo_aclaracion'] == 'tipo_dni'
    s = turn(s, 'Quiero pasar del DNI amarillo al azul')
    assert s['intencion'] == BLUE


def test_aclaracion_amarillo_conserva_consulta_coste(motor):
    service, retrieve, prompts = motor
    first = service.responder('¿Cuánto cuesta el DNI azul por primera vez?')
    sid, token = first['session_id'], first['session_token']
    assert '¿Ya dispone de DNI amarillo' in first['respuesta']
    assert not retrieve.called and not prompts
    result = service.responder('Ya tengo el amarillo', sid, token)
    assert result['intencion'] == BLUE and '€7' in result['respuesta']
    assert state(service, sid)['tipo_consulta'] == 'coste'
    assert result['session_id'] == sid and result['session_token'] == token


def test_cambio_a_titular_adulto_no_reutiliza_amarillo_azul(motor):
    service, _, _ = motor
    first = service.responder('Mi hija tiene 17 años y necesita cambiar DNI amarillo a azul')
    result = service.responder('Ahora quiero renovar mi DNI, soy adulto', first['session_id'], first['session_token'])
    s = state(service, first['session_id'])
    assert s['tramite_actual'] == 'dni_adulto_renovacion'
    assert result['intencion'] == 'general' and not result['fuentes']
    assert s['contexto_canonico']['titular']['valor'] == 'propio'


def test_api_nuevo_tramite_credencial_y_borrado(motor):
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        first = client.post('/api/v1/consultas', json={'pregunta': 'Quiero cambiar mi DNI amarillo a azul'})
        assert first.status_code == 200 and first.json()['intencion'] == BLUE
        sid, token = first.json()['session_id'], first.headers['X-Session-Token']
        assert 'session_token' not in first.json()
        cost = client.post('/api/v1/consultas', json={'pregunta': '¿Cuánto cuesta?', 'session_id': sid},
                           headers={'X-Session-Token': token})
        assert cost.status_code == 200 and '€7' in cost.json()['respuesta']
        assert client.delete('/api/v1/sesiones/' + sid, headers={'X-Session-Token': token}).status_code == 204
        fresh = client.post('/api/v1/consultas', json={'pregunta': '¿Cuánto cuesta el DNI azul por primera vez?'})
        assert fresh.json()['intencion'] == 'general' and not fresh.json()['fuentes']


def test_primer_dni_no_resuelve_por_si_solo_ambiguedad_sobre_azul(motor):
    service, retrieve, prompts = motor
    first = service.responder('Mi hijo menor necesita renovar su DNI')
    sid, token = first['session_id'], first['session_token']
    service.responder('¿Cuánto cuesta el DNI azul por primera vez?', sid, token)
    before = retrieve.call_count, len(prompts)
    ambiguous = service.responder('Es su primer DNI', sid, token)
    assert ambiguous['intencion'] == 'general' and not ambiguous['fuentes']
    assert (retrieve.call_count, len(prompts)) == before
    resolved = service.responder('Nunca tuvo DNI', sid, token)
    assert resolved['intencion'] == 'dni_menor_primera_vez'
    assert {f['archivo'] for f in resolved['fuentes']} == {'dni_menor_primera_vez.txt'}


def test_incidencia_sin_tramite_confirma_solo_la_dificultad(motor):
    service, retrieve, prompts = motor
    result = service.responder('La página de reservas da error')
    assert 'Entiendo que la página de reservas muestra un error' in result['respuesta']
    assert result['intencion'] == 'general' and not result['fuentes']
    assert state(service, result['session_id'])['requiere_aclaracion']
    assert result['verificacion'] == 'ok'
    assert not retrieve.called and not prompts


@pytest.mark.parametrize('confirmation', [
    'Quiero cambiar mi DNI amarillo a azul, ya tengo DNI',
    'Mi hijo tiene 17 años y necesita cambiar DNI amarillo a azul, ya tiene DNI',
])
def test_integracion_peticion_azul_afirmativa_con_tenencia_rehabilita(confirmation, motor):
    service, _, _ = motor
    first = service.responder('Mi hijo tiene 17 años y necesita cambiar DNI amarillo a azul')
    sid, token = first['session_id'], first['session_token']
    service.responder('No quiero cambiar el DNI amarillo a azul', sid, token)
    result = service.responder(confirmation, sid, token)
    assert result['intencion'] == BLUE
    assert CAMBIO_AZUL not in state(service, sid)['contexto_canonico']['rechazadas']
    assert {f['archivo'] for f in result['fuentes']} == {BLUE + '.txt'}


@pytest.mark.parametrize('followup', ['¿Cuánto cuesta?', '¿Y las fotografías?',
    '¿Qué requisitos necesito?', '¿Dónde solicito la cita?', '¿Cuánto demora?'])
def test_integracion_documento_titular_azul_no_hereda_edad(followup, motor):
    service, retrieve, prompts = motor
    first = service.responder('Mi hijo tiene 17 años y necesita cambiar DNI amarillo a azul')
    sid, token = first['session_id'], first['session_token']
    before = retrieve.call_count, len(prompts)
    for q in ['¿Debo presentar el DNI de mi hijo de 25 años?',
              'Es el DNI del titular, mi hijo', followup]:
        result = service.responder(q, sid, token)
        assert result['intencion'] == 'general' and not result['fuentes']
        assert state(service, sid)['requiere_aclaracion']
        assert (retrieve.call_count, len(prompts)) == before
    result = service.responder('Es para mi hijo de 17 años', sid, token)
    assert result['intencion'] == BLUE
    assert {f['archivo'] for f in result['fuentes']} == {BLUE + '.txt'}


def test_integracion_tipo_dni_no_borra_rechazo_renovacion(motor):
    service, retrieve, prompts = motor
    first = service.responder('Necesito renovar el DNI de mi hijo de 10 años')
    sid, token = first['session_id'], first['session_token']
    service.responder('No quiero renovar', sid, token)
    service.responder('¿Cuánto cuesta el DNI azul por primera vez?', sid, token)
    before = retrieve.call_count, len(prompts)
    result = service.responder('Es para mi hijo de 10 años, ya tiene DNI', sid, token)
    assert result['intencion'] == 'general' and not result['fuentes']
    assert 'renovacion' in state(service, sid)['contexto_canonico']['rechazadas']
    assert (retrieve.call_count, len(prompts)) == before
    result = service.responder('Quiero renovar el DNI de mi hijo de 10 años', sid, token)
    assert result['intencion'] == 'dni_menor_renovacion'
