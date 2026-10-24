"""Regresión P2: dos eventos de una misma conversación con snapshots obsoletos."""
from threading import Event, Lock, Thread

import gradio as gr
import pytest
from fastapi.testclient import TestClient

from app import ui


def initialize(client, session_hash):
    assert client.get('/').status_code == 200
    response = client.post('/gradio_api/run/generar_session_id', json={
        'data': [], 'session_hash': session_hash,
    })
    assert response.status_code == 200


def post(client, endpoint, question, session_hash='same-browser'):
    return client.post('/gradio_api/run/' + endpoint, json={
        # Ambos envíos llevan el historial visual vacío del instante inicial.
        'data': [question, [], None], 'session_hash': session_hash,
    })


@pytest.mark.parametrize('legacy', [True, False], ids=['reproduce-original', 'fixed'])
def test_enter_y_boton_concurren_sin_perder_sesion(monkeypatch, entorno_aislado, legacy):
    service = entorno_aislado
    monkeypatch.setattr(ui, 'rag', service)
    # Reproducir la implementación original sin el nuevo cerrojo de process_api.
    original_process = gr.Blocks.process_api if legacy else type(ui.demo).process_api
    second_attempted = Event()
    async def tracked(self, *args, **kwargs):
        fn = kwargs['block_fn']
        if fn.api_name == 'responder_consulta_1':
            second_attempted.set()
        return await original_process(self, *args, **kwargs)
    monkeypatch.setattr(type(ui.demo), 'process_api', tracked)

    first_ready, release, second_done = Event(), Event(), Event()
    original_answer = service.responder
    calls, responses, errors = [], {}, []
    guard = Lock()
    def blocked_answer(*args, **kwargs):
        with guard:
            calls.append(kwargs['session_id'])
            first = len(calls) == 1
        result = original_answer(*args, **kwargs)
        if first:
            # La sesión existe en el backend, pero Gradio todavía no ha guardado
            # su credencial ni el historial de salida del primer evento.
            first_ready.set()
            if not release.wait(5):
                raise RuntimeError('Barrera de prueba vencida')
        return result
    monkeypatch.setattr(service, 'responder', blocked_answer)
    application = ui.crear_app_gradio()
    with TestClient(application) as browser, TestClient(application) as other:
        initialize(browser, 'same-browser')
        initialize(other, 'same-browser')  # Mismo hash, propietario HTTP distinto.
        def send_first():
            try:
                responses['first'] = post(browser, 'responder_consulta', 'Primera consulta de pasaporte.')
            except Exception as exc:
                errors.append(type(exc).__name__)
        def send_second():
            try:
                responses['second'] = post(browser, 'responder_consulta_1', 'Segunda consulta de pasaporte.')
            except Exception as exc:
                errors.append(type(exc).__name__)
            finally:
                second_done.set()
        a, b = Thread(target=send_first), Thread(target=send_second)
        a.start()
        try:
            assert first_ready.wait(3)
            b.start()
            assert second_attempted.wait(3)
            if legacy:
                # Antes de la corrección, el segundo evento llega sin token y
                # sustituye el estado por una sesión nueva al fallar autorización.
                assert second_done.wait(3)
                assert 'Consulta no completada' in responses['second'].json()['data'][4]
            else:
                assert not second_done.is_set()
                with guard:
                    assert len(calls) == 1
            independent = post(other, 'responder_consulta', 'Consulta de pasaporte de otro navegador.')
            assert independent.status_code == 200
            assert 'Sesión temporal:' in independent.json()['data'][4]
            assert not release.is_set()
        finally:
            release.set()
            a.join(5)
            if b.ident is not None:
                b.join(5)
        assert not a.is_alive() and not b.is_alive() and not errors
        assert responses['first'].status_code == 200 and responses['second'].status_code == 200
        if not legacy:
            first, second = responses['first'].json()['data'], responses['second'].json()['data']
            sid = first[4].split('Sesión temporal: ')[1]
            assert second[4].split('Sesión temporal: ')[1] == sid
            # El último resultado visual incluye ambos turnos pese al [] enviado.
            assert [''.join(block['text'] for block in m['content'] if block['type'] == 'text')
                    for m in second[1] if m['role'] == 'user'] == [
                'Primera consulta de pasaporte.', 'Segunda consulta de pasaporte.',
            ]
            state = service.grafo.get_state({'configurable': {'thread_id': sid}}).values
            assert len(state['historial']) == 2
            assert len(service.sessions.sessions) == 2  # Una por navegador.
            assert first[2] is None and second[2] is None  # Credencial no expuesta.


def test_historial_cliente_obsoleto_no_sustituye_historial_servidor(monkeypatch, entorno_aislado):
    monkeypatch.setattr(ui, 'rag', entorno_aislado)
    with TestClient(ui.crear_app_gradio()) as browser:
        initialize(browser, 'same-browser')
        first = post(browser, 'responder_consulta', 'Primera consulta de pasaporte.')
        second = post(browser, 'responder_consulta_1', 'Segunda consulta de pasaporte.')
        assert first.status_code == second.status_code == 200
        assert len(second.json()['data'][1]) == 4
        reset = browser.post('/gradio_api/run/nueva_conversacion', json={
            'data': [None], 'session_hash': 'same-browser',
        })
        assert reset.status_code == 200
        assert not list(entorno_aislado.grafo.checkpointer.list(None))
        third = post(browser, 'responder_consulta', 'Consulta de pasaporte tras reinicio.')
        assert len(third.json()['data'][1]) == 2


def test_cola_enter_y_boton_publica_ambos_turnos_en_orden(monkeypatch, entorno_aislado):
    import json

    service = entorno_aislado
    monkeypatch.setattr(ui, 'rag', service)
    first_ready, second_attempted, release = Event(), Event(), Event()
    original_answer = service.responder
    count = [0]
    guard = Lock()
    def blocked_answer(*args, **kwargs):
        with guard:
            count[0] += 1
            first = count[0] == 1
        result = original_answer(*args, **kwargs)
        if first:
            first_ready.set()
            if not release.wait(5):
                raise RuntimeError('Barrera de prueba vencida')
        return result
    monkeypatch.setattr(service, 'responder', blocked_answer)
    original_process = type(ui.demo).process_api
    async def tracked(self, *args, **kwargs):
        if kwargs['block_fn'].api_name == 'responder_consulta_1':
            second_attempted.set()
        return await original_process(self, *args, **kwargs)
    monkeypatch.setattr(type(ui.demo), 'process_api', tracked)
    indices = {fn.api_name: k for k, fn in ui.demo.fns.items()}
    application = ui.crear_app_gradio()
    with TestClient(application) as browser, TestClient(application) as other:
        initialize(browser, 'same-browser')
        initialize(other, 'same-browser')
        try:
            for endpoint, question in [
                ('responder_consulta', 'Primera consulta de pasaporte.'),
                ('responder_consulta_1', 'Segunda consulta de pasaporte.'),
            ]:
                response = browser.post('/gradio_api/queue/join', json={
                    'data': [question, [], None], 'session_hash': 'same-browser',
                    'fn_index': indices[endpoint],
                })
                assert response.status_code == 200
                if endpoint == 'responder_consulta':
                    assert first_ready.wait(3)
            assert second_attempted.wait(3)
            with guard:
                assert count[0] == 1  # Segundo evento espera antes de leer gr.State.
            independent = post(other, 'responder_consulta', 'Consulta de pasaporte independiente.')
            assert 'Sesión temporal:' in independent.json()['data'][4]
        finally:
            release.set()
        stream = browser.get('/gradio_api/queue/data', params={'session_hash': 'same-browser'})
        events = [json.loads(line[6:]) for line in stream.text.splitlines() if line.startswith('data: ')]
        completed = [event for event in events if event.get('msg') == 'process_completed']
        assert len(completed) == 2 and all(event['success'] for event in completed)
        outputs = [event['output']['data'] for event in completed]
        assert [len(output[1]) for output in outputs] == [2, 4]
        ids = [output[4].split('Sesión temporal: ')[1] for output in outputs]
        assert ids[0] == ids[1]
        assert all(output[2] is None for output in outputs)
        assert len(service.grafo.get_state({'configurable': {'thread_id': ids[0]}}).values['historial']) == 2
