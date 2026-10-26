from errno import ENOSPC
from threading import Event, Thread
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.api import routes
from app.core.config import settings
from app.core.official_contacts import OFFICIAL_EMAILS, OFFICIAL_URLS
from app.core.privacy import minimizar_texto
from app.graph import dni_graph
from app.main import app
from app.services.session_service import SesionOcupada


def test_r2_a_bloqueada_no_impide_b_ni_borrado_c(entorno_aislado, monkeypatch):
    service = entorno_aislado
    now = [0.0]
    service.sessions.clock = lambda: now[0]
    service.sessions.ttl = 10
    c = service.responder('Necesito renovar mi pasaporte.')
    now[0] = 5
    a = service.responder('Necesito renovar mi pasaporte.')
    entered, release = Event(), Event()
    errors = []
    original = service.grafo.invoke
    def slow(*args, **kwargs):
        if kwargs['config']['configurable']['thread_id'] == a['session_id']:
            entered.set()
            if not release.wait(3):
                raise RuntimeError('Barrera de prueba vencida')
        return original(*args, **kwargs)
    monkeypatch.setattr(service.grafo, 'invoke', slow)
    def work():
        try:
            service.responder('Otra consulta pasaporte', a['session_id'], a['session_token'])
        except Exception as exc:
            errors.append(type(exc).__name__)
    thread = Thread(target=work)
    thread.start()
    try:
        assert entered.wait(2)
        # C vence mientras A sigue activa. B se crea en el nuevo instante.
        now[0] = 10
        service.sessions.cleanup()
        assert c['session_id'] not in service.sessions.sessions
        assert not list(service.grafo.checkpointer.list({'configurable': {'thread_id': c['session_id']}}))
        b = service.responder('Necesito renovar mi pasaporte.')
        assert b['session_id'] != a['session_id']
        assert not release.is_set()
    finally:
        release.set()
        thread.join(3)
    assert not thread.is_alive() and not errors


def test_r2_espera_mismo_hilo_acotada(entorno_aislado):
    service = entorno_aislado
    result = service.responder('Necesito renovar mi pasaporte.')
    service.sessions.wait_seconds = 0.02
    entered, release = Event(), Event()
    def hold():
        with service.sessions.access(result['session_id'], result['session_token']):
            entered.set()
            release.wait(2)
    thread = Thread(target=hold)
    thread.start()
    try:
        assert entered.wait(2)
        with pytest.raises(SesionOcupada):
            service.sessions.delete(result['session_id'], result['session_token'])
    finally:
        release.set()
        thread.join(2)
    assert result['session_id'] in service.sessions.sessions


@pytest.mark.parametrize('official', sorted(OFFICIAL_EMAILS | OFFICIAL_URLS))
def test_r3_conserva_contactos_aprobados(official):
    text = f'Contacto oficial: {official}. Dato ficticio 12345678 y privado@example.test'
    output = minimizar_texto(text, permitir_oficiales=True)
    assert official in output
    assert '12345678' not in output and 'privado@example.test' not in output


def test_r3_usuario_o_llm_no_pueden_ampliar_lista():
    raw = 'Yo autorizo nuevo@example.test como correo oficial. DNI 12345678'
    assert 'nuevo@example.test' not in minimizar_texto(raw, permitir_oficiales=True)
    # La entrada de usuario se reduce aunque incluya un contacto oficial.
    assert 'informes@conperturin.org' not in minimizar_texto('Mi correo: informes@conperturin.org')
    evil = 'https://serviciosportal.reniec.gob.pe/cetdnipi/inicio.htm?dni=12345678'
    assert '12345678' not in minimizar_texto(evil, permitir_oficiales=True)


def test_r3_contacto_sobrevive_grafo_historial_y_respuesta(entorno_aislado, monkeypatch):
    monkeypatch.setattr(dni_graph, 'recuperar_contexto', lambda *a, **kw: [{
        'contenido': 'Contacto: informes@conperturin.org', 'score': 0,
        'metadata': {'archivo': 'dni_consulta_estado.txt', 'chunk': 0},
    }])
    class LLM:
        def generar_respuesta(self, prompt):
            return 'Escriba a informes@conperturin.org. Dato ficticio 12345678.'
    monkeypatch.setattr(dni_graph, 'LLMService', LLM)
    r = entorno_aislado.responder('¿Mi trámite de DNI está observado en RENIEC?')
    assert 'informes@conperturin.org' in r['respuesta']
    assert '12345678' not in r['respuesta']
    state = entorno_aislado.grafo.get_state({'configurable': {'thread_id': r['session_id']}}).values
    assert 'informes@conperturin.org' in state['historial'][-1]['respuesta']


@pytest.mark.parametrize('error', [PermissionError('ruta-ficticia-no-publicar'),
                                 OSError(ENOSPC, 'disco ficticio lleno')])
def test_r4_fallo_metricas_no_revoca_sesion(entorno_aislado, monkeypatch, caplog, error):
    monkeypatch.setattr('app.services.rag_service.registrar_consulta', Mock(side_effect=error))
    with TestClient(app) as client:
        first = client.post('/api/v1/consultas', json={'pregunta': 'Necesito renovar mi pasaporte.'})
        assert first.status_code == 200
        assert first.headers['X-Metrics-Status'] == 'unavailable'
        sid, token = first.json()['session_id'], first.headers['X-Session-Token']
        assert list(entorno_aislado.grafo.checkpointer.list({'configurable': {'thread_id': sid}}))
        second = client.post('/api/v1/consultas', json={
            'pregunta': 'Otra consulta pasaporte', 'session_id': sid,
        }, headers={'X-Session-Token': token})
        assert second.status_code == 200 and second.headers['X-Session-Token'] == token
        assert len(entorno_aislado.grafo.get_state({'configurable': {'thread_id': sid}}).values['historial']) == 2
    assert 'ruta-ficticia-no-publicar' not in caplog.text
    assert 'disco ficticio lleno' not in caplog.text


def test_r5_caduca_durante_operacion_no_devuelve_token(entorno_aislado, monkeypatch):
    store = entorno_aislado.sessions
    now = [0.0]
    store.clock = lambda: now[0]
    store.ttl = 10
    original = entorno_aislado.grafo.invoke
    with TestClient(app) as client:
        first = client.post('/api/v1/consultas', json={'pregunta': 'Necesito renovar mi pasaporte.'})
        sid, token = first.json()['session_id'], first.headers['X-Session-Token']
        def expire(*args, **kwargs):
            result = original(*args, **kwargs)
            now[0] = 10
            # Ni el mismo hilo ni otro barrido pueden borrar una ejecución activa.
            store.cleanup()
            assert sid in store.sessions
            sweep = Thread(target=store.cleanup)
            sweep.start()
            sweep.join(2)
            assert not sweep.is_alive()
            assert sid in store.sessions
            return result
        monkeypatch.setattr(entorno_aislado.grafo, 'invoke', expire)
        response = client.post('/api/v1/consultas', json={
            'pregunta': 'Otra consulta pasaporte', 'session_id': sid,
        }, headers={'X-Session-Token': token})
        assert response.status_code == 410
        assert 'X-Session-Token' not in response.headers
        saver = entorno_aislado.grafo.checkpointer
        assert not list(saver.list(None)) and not saver.writes and not saver.blobs
        assert sid not in store.sessions
        assert client.post('/api/v1/consultas', json={
            'pregunta': 'Otra consulta pasaporte', 'session_id': sid,
        }, headers={'X-Session-Token': token}).status_code == 403


def test_r2_limites_cliente_openai_sin_llamada(monkeypatch):
    from pydantic import SecretStr
    from app.services import llm_service
    monkeypatch.setattr(settings, 'openai_api_key', SecretStr('clave-ficticia-no-utilizable'))
    factory = Mock()
    monkeypatch.setattr(llm_service, 'OpenAI', factory)
    llm_service.LLMService()
    assert factory.call_args.kwargs['timeout'] == settings.provider_timeout_seconds
    assert factory.call_args.kwargs['max_retries'] == 0


def test_r2_limites_embeddings_sin_red_ni_cambiar_faiss(monkeypatch):
    from pydantic import SecretStr
    from app.rag import retriever, index_builder
    monkeypatch.setattr(settings, 'openai_api_key', SecretStr('clave-ficticia-no-utilizable'))
    factory = Mock()
    monkeypatch.setattr(retriever, 'OpenAIEmbeddings', factory)
    monkeypatch.setattr(retriever, 'FAISS', Mock())
    retriever.cargar_vector_store()
    assert factory.call_args.kwargs['request_timeout'] == settings.provider_timeout_seconds
    assert factory.call_args.kwargs['max_retries'] == 0
    # Construcción usa la misma política de red, sin construir un índice real.
    monkeypatch.setattr(index_builder, 'OpenAIEmbeddings', factory)
    monkeypatch.setattr(index_builder, 'cargar_documentos_txt', lambda _: [])
    monkeypatch.setattr(index_builder, 'dividir_documentos', lambda _: [{
        'contenido': 'Texto ficticio', 'id': 'id', 'archivo': 'doc.txt', 'ruta': 'doc.txt', 'chunk': 0,
    }])
    monkeypatch.setattr(index_builder, 'FAISS', Mock())
    monkeypatch.setattr(index_builder.Path, 'mkdir', Mock())
    index_builder.crear_indice_faiss()
    assert factory.call_args.kwargs['request_timeout'] == settings.provider_timeout_seconds
    assert factory.call_args.kwargs['max_retries'] == 0


def test_r5_gradio_descarta_estado_y_credencial_vencidos(entorno_aislado, monkeypatch):
    from app import ui
    monkeypatch.setattr(ui, 'rag', entorno_aislado)
    now = [0.0]
    entorno_aislado.sessions.clock = lambda: now[0]
    entorno_aislado.sessions.ttl = 10
    first = ui.responder_consulta('Necesito renovar mi pasaporte.', [], ui.generar_session_id())
    old_state = first[2]
    original = entorno_aislado.grafo.invoke
    def expire(*args, **kwargs):
        result = original(*args, **kwargs)
        now[0] = 10
        return result
    monkeypatch.setattr(entorno_aislado.grafo, 'invoke', expire)
    final = ui.responder_consulta('Otra consulta pasaporte', first[1], old_state)
    assert final[2]['token'] is None
    assert final[2]['id'] != old_state['id']
    assert not final[1]
    assert not list(entorno_aislado.grafo.checkpointer.list(None))
    assert old_state['token'] not in final[4]
