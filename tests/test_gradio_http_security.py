import pytest
from fastapi.testclient import TestClient

from app import ui


@pytest.fixture
def gradio_app(monkeypatch, entorno_aislado):
    monkeypatch.setattr(ui, 'rag', entorno_aislado)
    return ui.crear_app_gradio()


def load(client, session_hash):
    r = client.post('/gradio_api/run/generar_session_id', json={'data': [], 'session_hash': session_hash})
    assert r.status_code == 200
    return r


def answer(client, session_hash, question='Necesito renovar mi pasaporte.'):
    r = client.post('/gradio_api/run/responder_consulta', json={
        'data': [question, [], None], 'session_hash': session_hash,
    })
    assert r.status_code == 200
    assert 'Sesión temporal:' in r.json()['data'][4]
    return r


def test_r1_dos_clientes_mismo_hash_no_comparten_estado_ni_secretos(gradio_app, entorno_aislado):
    with TestClient(gradio_app) as a, TestClient(gradio_app) as b:
        assert a.get('/').status_code == 200
        assert b.get('/').status_code == 200
        load(a, 'hash-conocido')
        first = answer(a, 'hash-conocido')
        sid_a = first.json()['data'][4].split('Sesión temporal: ')[1]
        owner_hash = next(iter(ui.demo.state_holder.session_data))
        tokens = [value['token'] for state in ui.demo.state_holder.session_data.values()
                  for value in state.state_data.values()
                  if isinstance(value, dict) and value.get('token')]
        assert tokens
        # B presenta deliberadamente el mismo hash. El namespace es distinto.
        load(b, 'hash-conocido')
        second = answer(b, 'hash-conocido')
        sid_b = second.json()['data'][4].split('Sesión temporal: ')[1]
        assert sid_a != sid_b
        state_a = entorno_aislado.grafo.get_state({'configurable': {'thread_id': sid_a}}).values
        assert len(state_a['historial']) == 1
        # Intentar reiniciar mediante el hash ajeno solo elimina la sesión de B.
        reset = b.post('/gradio_api/run/nueva_conversacion', json={'data': [None], 'session_hash': 'hash-conocido'})
        assert reset.status_code == 200
        assert sid_a in entorno_aislado.sessions.sessions
        assert sid_b not in entorno_aislado.sessions.sessions
        assert first.json()['data'][2] is None and second.json()['data'][2] is None
        exposed = first.text + second.text + a.get('/config').text + b.get('/config').text
        assert 'session_token' not in exposed
        assert all(token not in exposed for token in tokens)
        # Ni siquiera el hash interno revelado permite seleccionar el estado de A.
        load(b, owner_hash)
        third = answer(b, owner_hash)
        assert sid_a not in third.json()['data'][4]
        assert all(token not in third.text for token in tokens)
        assert b.get('/gradio_api/deep_link', params={'session_hash': 'hash-conocido'}).status_code == 403
        # A sigue operando con su propia cookie y hash.
        answer(a, 'hash-conocido', 'Otra consulta pasaporte')
        assert len(entorno_aislado.grafo.get_state({'configurable': {'thread_id': sid_a}}).values['historial']) == 2


def test_r1_sin_cookie_cookie_alterada_y_origen_ajeno(gradio_app):
    with TestClient(gradio_app) as client:
        payload = {'data': [], 'session_hash': 'hash-conocido'}
        assert client.post('/gradio_api/run/generar_session_id', json=payload).status_code == 403
        response = client.get('/')
        assert 'HttpOnly' in response.headers['set-cookie'] and 'SameSite=Strict' in response.headers['set-cookie']
        assert client.post('/gradio_api/run/generar_session_id', json=payload,
                           headers={'Origin': 'https://sitio-ajeno.invalid'}).status_code == 403
        client.cookies.set('tfm_gradio_owner', 'cookie.alterada.invalida')
        assert client.post('/gradio_api/run/generar_session_id', json=payload).status_code == 403


def test_r1_cookie_vencida_no_recupera_estado(gradio_app):
    now = [100.0]
    gradio_app.clock = lambda: now[0]
    with TestClient(gradio_app) as client:
        client.get('/')
        load(client, 'hash-conocido')
        now[0] += gradio_app.ttl + 1
        assert client.post('/gradio_api/run/generar_session_id', json={
            'data': [], 'session_hash': 'hash-conocido',
        }).status_code == 403


def test_r1_cola_y_sse_del_navegador_aisladas(gradio_app, entorno_aislado):
    with TestClient(gradio_app) as a, TestClient(gradio_app) as b:
        a.get('/')
        b.get('/')
        load(a, 'hash-cola-compartido')
        fn_index = next(k for k, fn in ui.demo.fns.items() if fn.api_name == 'responder_consulta')
        queued = a.post('/gradio_api/queue/join', json={
            'data': ['Necesito renovar mi pasaporte.', [], None],
            'fn_index': fn_index, 'session_hash': 'hash-cola-compartido',
        })
        assert queued.status_code == 200
        stolen = b.get('/gradio_api/queue/data', params={'session_hash': 'hash-cola-compartido'})
        assert 'process_completed' not in stolen.text
        events = a.get('/gradio_api/queue/data', params={'session_hash': 'hash-cola-compartido'})
        assert 'process_completed' in events.text
        assert len(entorno_aislado.sessions.sessions) == 1
        sid = next(iter(entorno_aislado.sessions.sessions))
        assert sid not in stolen.text
        assert 'session_token' not in events.text


def test_r1_cookie_https_y_rutas_auxiliares_bloqueadas(gradio_app):
    gradio_app.secure = True
    with TestClient(gradio_app, base_url='https://testserver') as client:
        response = client.get('/')
        assert 'Secure' in response.headers['set-cookie']
        load(client, 'hash-https')
        for path in ('/gradio_api/deep_link', '/gradio_api/call/responder_consulta',
                     '/gradio_api/file=state.json', '/monitoring'):
            assert client.get(path).status_code == 403
