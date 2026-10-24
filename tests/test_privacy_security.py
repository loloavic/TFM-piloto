from threading import Event
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api import routes
from app.core.config import settings
from app.core.privacy import minimizar_texto
from app.graph import dni_graph
from app.main import app
from app.services import evaluation_service, log_service
from app.services.session_service import (
    CapacidadSesionesAgotada, SesionNoAutorizada, SessionStore,
)

ADMIN = {'Authorization': 'Bearer test-admin-only'}
PUBLIC = '/api/v1/consultas'


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def generacion_local(monkeypatch):
    """Grafo/checkpointer reales, únicamente recuperación y proveedor simulados."""
    prompts = []
    def recuperar_local(query, **kwargs):
        prompts.append('CONSULTA EMBEDDINGS: ' + query)
        return [{
        'contenido': 'La tasa documentada es 5 euros.', 'score': 0.1,
        'metadata': {'archivo': 'dni_menor_renovacion.txt', 'chunk': 0},
        }]
    monkeypatch.setattr(dni_graph, 'recuperar_contexto', recuperar_local)
    class FakeLLM:
        def generar_respuesta(self, prompt):
            prompts.append(prompt)
            return 'Tasa 5 euros. Dato ficticio 87654321 y ejemplo@example.test.'
    monkeypatch.setattr(dni_graph, 'LLMService', FakeLLM)
    return prompts


@pytest.mark.parametrize('endpoint', ['/evaluacion/resumen', '/evaluacion/consultas'])
@pytest.mark.parametrize('headers', [{}, {'Authorization': 'Bearer incorrecto'}])
def test_registros_rechazan_clientes_no_autorizados(client, endpoint, headers):
    assert client.get('/api/v1' + endpoint, headers=headers).status_code == 401


@pytest.mark.parametrize('endpoint', ['/evaluacion/resumen', '/evaluacion/consultas'])
def test_registros_admin_y_configuracion_cerrada(client, monkeypatch, endpoint):
    assert client.get('/api/v1' + endpoint, headers=ADMIN).status_code == 200
    monkeypatch.setattr(settings, 'internal_api_token', None)
    assert client.get('/api/v1' + endpoint, headers=ADMIN).status_code == 503


def test_consulta_publica_y_sesion_ajena(client):
    r = client.post(PUBLIC, json={'pregunta': 'Necesito renovar mi pasaporte.'})
    assert r.status_code == 200
    sid, token = r.json()['session_id'], r.headers['X-Session-Token']
    assert r.headers['Cache-Control'] == 'no-store'
    before = len(list(routes.rag.grafo.checkpointer.list(None)))
    payload = {'pregunta': 'Otra consulta de pasaporte.', 'session_id': sid}
    for headers in ({}, {'X-Session-Token': 'incorrecto'}):
        assert client.post(PUBLIC, json=payload, headers=headers).status_code == 403
    assert len(list(routes.rag.grafo.checkpointer.list(None))) == before
    assert client.post(PUBLIC, json=payload, headers={'X-Session-Token': token}).status_code == 200
    second = client.post(PUBLIC, json={'pregunta': 'Otra consulta de pasaporte.'})
    assert second.json()['session_id'] != sid
    assert client.post(PUBLIC, json=payload, headers={
        'X-Session-Token': second.headers['X-Session-Token'],
    }).status_code == 403


def test_borrado_autorizado_elimina_todos_los_artefactos(client):
    r = client.post(PUBLIC, json={'pregunta': 'Necesito renovar mi pasaporte.'})
    sid, token = r.json()['session_id'], r.headers['X-Session-Token']
    url = '/api/v1/sesiones/' + sid
    assert client.delete(url).status_code == 403
    assert client.delete(url, headers={'X-Session-Token': 'incorrecto'}).status_code == 403
    saver = routes.rag.grafo.checkpointer
    assert list(saver.list({'configurable': {'thread_id': sid}}))
    assert client.delete(url, headers={'X-Session-Token': token}).status_code == 204
    assert sid not in saver.storage
    assert not any(key[0] == sid for key in saver.writes)
    assert not any(key[0] == sid for key in saver.blobs)
    assert sid not in routes.rag.sessions.sessions
    assert client.post(PUBLIC, json={'pregunta': 'Hola otra vez', 'session_id': sid},
                       headers={'X-Session-Token': token}).status_code == 403


def test_caducidad_absoluta_y_no_resurreccion(client):
    now = [0.0]
    store = routes.rag.sessions
    store.clock = lambda: now[0]
    store.ttl = 10
    r = client.post(PUBLIC, json={'pregunta': 'Necesito renovar mi pasaporte.'})
    sid, token = r.json()['session_id'], r.headers['X-Session-Token']
    now[0] = 9
    assert client.post(PUBLIC, json={'pregunta': 'Otra consulta pasaporte', 'session_id': sid},
                       headers={'X-Session-Token': token}).status_code == 200
    now[0] = 10
    store.cleanup()
    saver = routes.rag.grafo.checkpointer
    assert not list(saver.list(None))
    assert not saver.writes and not saver.blobs
    assert client.post(PUBLIC, json={'pregunta': 'Otra consulta pasaporte', 'session_id': sid},
                       headers={'X-Session-Token': token}).status_code == 403


def test_barrido_periodico_sin_nuevas_peticiones():
    deleted = Event()
    now = [0.0]
    store = SessionStore(lambda sid: deleted.set(), ttl=10, maximum=2, clock=lambda: now[0])
    with store.access('synthetic-thread', None):
        pass
    now[0] = 10
    store.start(0.01)
    try:
        assert deleted.wait(2)
        with store.lock:
            assert not store.sessions
    finally:
        store.close()


def test_capacidad_y_credencial_no_valida_no_crean_hilos():
    store = SessionStore(Mock(), ttl=10, maximum=1)
    with store.access('uno', None) as token:
        assert store.sessions['uno'].digest != token.encode()
    with pytest.raises(SesionNoAutorizada):
        with store.access('otro', 'inventado'):
            pass
    with pytest.raises(CapacidadSesionesAgotada):
        with store.access('otro', None):
            pass
    store.close()
    assert not store.sessions


@pytest.mark.parametrize('text,secret', [
    ('DNI 12345678', '12345678'),
    ('Pasaporte AB1234567', 'AB1234567'),
    ('correo ejemplo@example.test', 'ejemplo@example.test'),
    ('llame al +39 333 123 4567', '+39 333 123 4567'),
])
def test_redaccion_parcial_de_identificadores(text, secret):
    assert secret not in minimizar_texto(text)


def test_no_se_promete_anonimizacion_general():
    assert minimizar_texto('Me llamo Persona Ficticia') == 'Me llamo Persona Ficticia'
    assert minimizar_texto('Renovar el DNI de mi hijo cuesta 5 euros') == 'Renovar el DNI de mi hijo cuesta 5 euros'


def test_minimizacion_antes_del_proveedor_y_de_cada_checkpoint(client, generacion_local):
    raw = 'Quiero renovar el DNI de mi hijo menor. DNI 12345678 correo ejemplo@example.test'
    r = client.post(PUBLIC, json={'pregunta': raw})
    assert r.status_code == 200
    assert generacion_local
    checkpoints = list(routes.rag.grafo.checkpointer.list(None))
    inspected = str(checkpoints) + str(generacion_local) + r.text
    for secret in ('12345678', '87654321', 'ejemplo@example.test'):
        assert secret not in inspected
    sid = r.json()['session_id']
    state = routes.rag.grafo.get_state({'configurable': {'thread_id': sid}}).values
    assert '[IDENTIFICADOR REDACTADO]' in state['pregunta']
    assert '87654321' not in state['historial'][-1]['respuesta']
    # Un segundo turno verifica el historial que llega al proveedor simulado.
    client.post(PUBLIC, json={'pregunta': '¿Y qué requisitos necesito?', 'session_id': sid},
                headers={'X-Session-Token': r.headers['X-Session-Token']})
    assert '12345678' not in str(generacion_local)


def test_metricas_no_guardan_textos_y_lector_no_expone_texto_legacy():
    log_service.registrar_consulta('DNI 12345678', 'ejemplo@example.test',
                                  'texto no confiable', 'observada: DNI 12345678',
                                  [{'archivo': 'ejemplo@example.test'}])
    contents = log_service.LOG_PATH.read_text()
    assert '12345678' not in contents and 'ejemplo@example.test' not in contents
    assert 'texto no confiable' not in contents
    log_service.LOG_PATH.write_text(
        'fecha_hora,pregunta,intencion,verificacion,respuesta,fuentes\n'
        '2026-01-01,DNI 12345678,general,ok,ejemplo@example.test,[]\n'
    )
    df = evaluation_service.cargar_log_consultas()
    assert df.iloc[0]['pregunta'] == '' and df.iloc[0]['respuesta'] == ''


def test_fallo_parcial_borra_checkpoints(client, monkeypatch):
    original = routes.rag.grafo.invoke
    sid = str(uuid4())
    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError('fallo sintético sin texto personal')
    monkeypatch.setattr(routes.rag.grafo, 'invoke', fail)
    with pytest.raises(RuntimeError):
        client.post(PUBLIC, json={'pregunta': 'Necesito renovar mi pasaporte.', 'session_id': sid})
    saver = routes.rag.grafo.checkpointer
    assert not list(saver.list(None)) and not saver.writes and not saver.blobs
    assert sid not in routes.rag.sessions.sessions


def test_cierre_borra_todos_los_hilos(entorno_aislado):
    service = entorno_aislado
    for _ in range(2):
        service.responder('Necesito renovar mi pasaporte.')
    assert len(service.sessions.sessions) == 2
    service.sessions.close()
    saver = service.grafo.checkpointer
    assert not list(saver.list(None)) and not saver.writes and not saver.blobs


def test_uuid_conocido_no_basta_y_no_hay_secreto_en_json(client):
    sid = str(uuid4())
    r = client.post(PUBLIC, json={'pregunta': 'Necesito renovar mi pasaporte.', 'session_id': sid})
    token = r.headers['X-Session-Token']
    assert token not in r.text
    assert 'session_token' not in r.json()
    assert token.encode() != routes.rag.sessions.sessions[sid].digest
    assert client.post(PUBLIC, json={'pregunta': 'Otra consulta pasaporte', 'session_id': sid}).status_code == 403


def test_borrado_de_un_hilo_no_borra_otro(client):
    first = client.post(PUBLIC, json={'pregunta': 'Necesito renovar mi pasaporte.'})
    second = client.post(PUBLIC, json={'pregunta': 'Necesito renovar mi pasaporte.'})
    sid = first.json()['session_id']
    client.delete('/api/v1/sesiones/' + sid, headers={'X-Session-Token': first.headers['X-Session-Token']})
    other = second.json()['session_id']
    assert list(routes.rag.grafo.checkpointer.list({'configurable': {'thread_id': other}}))


def test_error_no_refleja_token_en_respuesta(client):
    r = client.post(PUBLIC, json={'pregunta': 'Hola, una consulta', 'session_id': str(uuid4())},
                    headers={'X-Session-Token': 'credencial-ficticia-no-registrar'})
    assert r.status_code == 403
    assert 'credencial-ficticia-no-registrar' not in r.text


def test_borrado_espera_ejecucion_y_no_resucita_checkpoints(entorno_aislado, monkeypatch):
    from threading import Thread

    service = entorno_aislado
    first = service.responder('Necesito renovar mi pasaporte.')
    sid, token = first['session_id'], first['session_token']
    invoked, release, deleting, deleted = Event(), Event(), Event(), Event()
    errors = []
    original = service.grafo.invoke
    def blocked(*args, **kwargs):
        result = original(*args, **kwargs)
        invoked.set()
        assert release.wait(2)
        return result
    monkeypatch.setattr(service.grafo, 'invoke', blocked)
    def answer():
        try:
            service.responder('Otra consulta pasaporte', sid, token)
        except Exception as error:
            errors.append(type(error).__name__)
    def delete():
        deleting.set()
        service.sessions.delete(sid, token)
        deleted.set()
    running = Thread(target=answer)
    removal = Thread(target=delete)
    running.start()
    try:
        assert invoked.wait(2)
        removal.start()
        assert deleting.wait(2)
        assert not deleted.is_set()
    finally:
        release.set()
        running.join(2)
        if removal.ident is not None:
            removal.join(2)
    assert not running.is_alive() and not removal.is_alive()
    assert not errors and deleted.is_set()
    saver = service.grafo.checkpointer
    assert not list(saver.list(None)) and not saver.writes and not saver.blobs
