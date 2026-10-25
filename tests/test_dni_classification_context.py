import pytest

from app.graph.dni_graph import clasificar_intencion


@pytest.mark.parametrize('question,expected', [
    ('Soy adulto y quiero renovar mi DNI.', 'general'),
    ('No necesito pasaporte; quiero renovar el DNI de mi hijo menor.', 'dni_menor_renovacion'),
    ('¿Debo llevar mi pasaporte para el primer DNI de mi hijo menor?', 'dni_menor_primera_vez'),
    ('¿Las fotografías para renovar el DNI de mi hijo menor son tamaño pasaporte?', 'dni_menor_renovacion'),
    ('Necesito renovar el DNI de mi hijo.', 'general'),
])
def test_auditoria_clasificacion(question, expected):
    assert clasificar_intencion({'pregunta': question})['intencion'] == expected


@pytest.mark.parametrize('question,intent,active,group', [
    ('Necesito renovar el DNI de mi hijo de 10 años.', 'dni_menor_renovacion', 'dni_menor_renovacion', 'menor'),
    ('Mi hija de 17 años necesita su primer DNI.', 'dni_menor_primera_vez', 'dni_menor_primera_vez', 'menor'),
    ('Mi hijo de 18 años quiere renovar su DNI.', 'general', 'dni_adulto_renovacion', 'adulto'),
    ('Mi hijo adulto necesita su primer DNI.', 'general', 'dni_adulto_primera_vez', 'adulto'),
    ('Tengo 25 años y nunca he tenido DNI.', 'general', 'dni_adulto_primera_vez', 'adulto'),
    ('Tengo 17 años y quiero renovar mi DNI.', 'dni_menor_renovacion', 'dni_menor_renovacion', 'menor'),
    ('Soy menor de edad y necesito renovar mi DNI.', 'dni_menor_renovacion', 'dni_menor_renovacion', 'menor'),
    ('Soy adulto, necesito renovar el DNI de mi hijo de 10 años.', 'dni_menor_renovacion', 'dni_menor_renovacion', 'menor'),
    ('Soy adulto y quiero renovar mi DNI; mi hijo tiene 10 años.', 'general', 'dni_adulto_renovacion', 'adulto'),
    ('No quiero renovar el DNI de mi hijo menor porque nunca tuvo DNI.', 'dni_menor_primera_vez', 'dni_menor_primera_vez', 'menor'),
    ('No es primera vez: mi hijo menor ya tiene DNI vencido.', 'dni_menor_renovacion', 'dni_menor_renovacion', 'menor'),
    ('No es renovación, es la primera vez para mi hijo menor con DNI.', 'dni_menor_primera_vez', 'dni_menor_primera_vez', 'menor'),
    ('Necesito un pasaporte.', 'fuera_alcance', '', None),
    ('Necesito renovar mi pasaporte.', 'fuera_alcance', '', None),
    ('¿Debo presentar pasaporte para el primer DNI de mi hijo menor?', 'dni_menor_primera_vez', 'dni_menor_primera_vez', 'menor'),
    ('Necesito pasaporte para la primera inscripción de DNI de mi hijo menor.', 'dni_menor_primera_vez', 'dni_menor_primera_vez', 'menor'),
])
def test_titular_y_documentos_de_apoyo(question, intent, active, group):
    state = clasificar_intencion({'pregunta': question})
    assert state['intencion'] == intent
    assert state['tramite_actual'] == active
    assert state['contexto_solicitante'].get('grupo_edad') == group
    if 'adulto_' in active:
        assert not state['tramite_documentado']
        assert state['estado_documental'] == 'no_documentado'


@pytest.mark.parametrize('question', [
    'Quiero renovar mi DNI.',
    'Quiero el DNI de mi hijo menor.',
    'Mi hijo menor necesita renovar el DNI por primera vez.',
    'Quiero renovar el DNI de mi hijo de 10 años, pero nunca tuvo DNI.',
    'Quiero renovar el pasaporte y renovar el DNI de mi hijo menor.',
    'No es primera vez para el DNI de mi hijo menor.',
    'No quiero renovar mi DNI.',
])
def test_ambiguedades_y_contradicciones_aclaran(question):
    state = clasificar_intencion({'pregunta': question})
    assert state['intencion'] == 'general'
    assert state['requiere_aclaracion']
    assert state['estado_documental'] == 'pendiente_aclaracion'


def turn(state, question):
    return clasificar_intencion({**state, 'pregunta': question})


def test_plazo_no_sobrescribe_tramite():
    state = {}
    for question, topic in [
        ('Necesito renovar el DNI de mi hijo de 10 años.', 'otra'),
        ('¿Cuánto demora?', 'plazo'),
        ('¿Y cuánto cuesta?', 'coste'),
        ('¿Dónde solicito la cita?', 'cita'),
    ]:
        state = turn(state, question)
        assert state['intencion'] == 'dni_menor_renovacion'
        assert state['tramite_actual'] == 'dni_menor_renovacion'
        assert state['tipo_consulta'] == topic


def test_seguimiento_es_tema_no_nueva_operacion():
    state = turn({}, 'Necesito renovar el DNI de mi hijo de 10 años.')
    state = turn(state, '¿Dónde consulto el estado del trámite?')
    assert state['intencion'] == 'dni_consulta_estado'
    assert state['tramite_actual'] == 'dni_menor_renovacion'
    state = turn(state, '¿Y cuánto cuesta?')
    assert state['intencion'] == 'dni_menor_renovacion'


def test_aclaracion_edad_y_cambio_explicito():
    state = turn({}, 'Quiero renovar el DNI de mi hijo.')
    assert state['motivo_aclaracion'] == 'edad'
    state = turn(state, 'Tiene 10 años')
    assert state['intencion'] == 'dni_menor_renovacion'
    state = turn(state, 'No es renovación; es primera vez.')
    assert state['intencion'] == 'dni_menor_primera_vez'
    state = turn(state, 'Ahora es para mí: soy adulto y quiero renovar mi DNI.')
    assert state['tramite_actual'] == 'dni_adulto_renovacion'
    assert state['estado_documental'] == 'no_documentado'
    state = turn(state, 'Ahora quiero renovar el DNI de otro hijo.')
    assert state['motivo_aclaracion'] == 'edad'


def test_rechazo_explicito_no_reutiliza_operacion_negada():
    state = turn({}, 'Quiero renovar el DNI de mi hijo menor.')
    state = turn(state, 'No quiero renovar.')
    assert state['requiere_aclaracion'] and not state['operacion_dni']
    state = turn(state, 'Es su primer DNI')
    assert state['intencion'] == 'dni_menor_primera_vez'


def test_fuera_de_alcance_borra_contexto_y_no_retorna_por_inercia():
    state = turn({}, 'Quiero renovar el DNI de mi hijo menor.')
    state = turn(state, 'Ahora necesito renovar mi pasaporte.')
    assert state['intencion'] == 'fuera_alcance'
    assert not state['tramite_actual'] and not state['contexto_solicitante']
    state = turn(state, '¿Y cuánto cuesta?')
    assert state['requiere_aclaracion']


@pytest.mark.parametrize('question,expected', [
    ('No quiero renovar mi DNI; es el primer DNI de mi hijo de 10 años.', 'dni_menor_primera_vez'),
    ('¿Dónde consulto el estado de mi pasaporte?', 'fuera_alcance'),
    ('Necesito revisar los requisitos para renovar el DNI de mi hijo menor.', 'dni_menor_renovacion'),
    ('No tengo DNI.', 'general'),
    ('No quiero consultar el estado; quiero requisitos para renovar el DNI de mi hijo menor.', 'dni_menor_renovacion'),
])
def test_negaciones_y_palabras_no_son_tramites(question, expected):
    assert turn({}, question)['intencion'] == expected


def test_pasaporte_sin_objetivo_es_ambiguo_en_contexto_dni():
    state = turn({}, 'Quiero renovar el DNI de mi hijo menor.')
    state = turn(state, '¿Y el pasaporte?')
    assert state['requiere_aclaracion'] and state['intencion'] == 'general'


@pytest.fixture
def motor_local(monkeypatch, entorno_aislado):
    from pathlib import Path
    from app.graph import dni_graph
    calls = {'retrieval': [], 'llm': []}
    documents = [{
        'contenido': path.read_text(encoding='utf-8'), 'score': 0.1,
        'metadata': {'archivo': path.name, 'chunk': 0},
    } for path in Path('data/raw').glob('*.txt')]
    def retrieve(question, **kwargs):
        calls['retrieval'].append(question)
        return documents
    class LocalLLM:
        def generar_respuesta(self, prompt):
            calls['llm'].append(prompt)
            return 'Respuesta simulada para verificar el flujo documental.'
    monkeypatch.setattr(dni_graph, 'recuperar_contexto', retrieve)
    monkeypatch.setattr(dni_graph, 'LLMService', LocalLLM)
    return entorno_aislado, calls


def graph_state(service, sid):
    return service.grafo.get_state({'configurable': {'thread_id': sid}}).values


def test_grafo_real_cuatro_turnos_conserva_operacion_y_fuentes(motor_local):
    service, calls = motor_local
    sid = token = None
    for question, topic in [
        ('Necesito renovar el DNI de mi hijo de 10 años.', 'otra'),
        ('¿Cuánto demora?', 'plazo'),
        ('¿Y cuánto cuesta?', 'coste'),
        ('¿Dónde solicito la cita?', 'cita'),
    ]:
        result = service.responder(question, sid, token)
        sid, token = result['session_id'], result['session_token']
        state = graph_state(service, sid)
        assert state['tramite_actual'] == 'dni_menor_renovacion'
        assert state['tipo_consulta'] == topic
        assert result['intencion'] == 'dni_menor_renovacion'
        assert {source['archivo'] for source in result['fuentes']} == {'dni_menor_renovacion.txt'}
    assert len(state['historial']) == 4 and len(calls['llm']) == 4
    assert 'seguimiento RENIEC avance 100%' not in calls['retrieval'][1]
    assert 'renovación de DNI de menor de edad' in calls['retrieval'][1]


def test_grafo_seguimiento_y_cambio_de_procedimiento(motor_local):
    service, _ = motor_local
    first = service.responder('Quiero renovar el DNI de mi hijo menor.')
    sid, token = first['session_id'], first['session_token']
    following = service.responder('¿Dónde consulto el estado del trámite?', sid, token)
    assert following['intencion'] == 'dni_consulta_estado'
    assert {s['archivo'] for s in following['fuentes']} == {'dni_consulta_estado.txt'}
    assert graph_state(service, sid)['tramite_actual'] == 'dni_menor_renovacion'
    cost = service.responder('¿Y cuánto cuesta?', sid, token)
    assert cost['intencion'] == 'dni_menor_renovacion'
    change = service.responder('Ahora es el primer DNI de mi hija de 10 años.', sid, token)
    assert change['intencion'] == 'dni_menor_primera_vez'
    assert {s['archivo'] for s in change['fuentes']} == {'dni_menor_primera_vez.txt'}


@pytest.mark.parametrize('question,word', [
    ('Soy adulto y quiero renovar mi DNI.', 'no documenta'),
    ('Quiero renovar el DNI de mi hijo.', 'menor de 18'),
    ('Quiero el DNI de mi hijo menor.', 'primer DNI'),
])
def test_abstencion_y_aclaracion_no_llaman_proveedor(motor_local, question, word):
    service, calls = motor_local
    result = service.responder(question)
    assert word in result['respuesta']
    assert result['fuentes'] == [] and result['intencion'] == 'general'
    assert result['verificacion'] == 'ok'
    assert not calls['retrieval'] and not calls['llm']
    if 'adulto' in question:
        state = graph_state(service, result['session_id'])
        assert state['tramite_actual'] == 'dni_adulto_renovacion'
        assert not state['requiere_aclaracion']


def test_sin_fragmentos_no_inventa_y_preserva_identificacion(motor_local, monkeypatch):
    from app.graph import dni_graph
    service, calls = motor_local
    monkeypatch.setattr(dni_graph, 'recuperar_contexto', lambda *a, **kw: [])
    result = service.responder('Quiero renovar el DNI de mi hijo menor.')
    assert result['intencion'] == 'dni_menor_renovacion'
    assert not result['fuentes'] and not calls['llm']
    state = graph_state(service, result['session_id'])
    assert state['tramite_actual'] == 'dni_menor_renovacion'
    assert state['estado_documental'] == 'sin_evidencia'
    assert 'No cuento con información documental suficiente' in result['respuesta']


def test_reinicio_y_aislamiento_no_reutilizan_contexto(motor_local):
    service, _ = motor_local
    first = service.responder('Quiero renovar el DNI de mi hijo menor.')
    sid, token = first['session_id'], first['session_token']
    other = service.responder('¿Y cuánto cuesta?')
    assert other['intencion'] == 'general'
    assert not graph_state(service, other['session_id'])['operacion_dni']
    assert graph_state(service, sid)['tramite_actual'] == 'dni_menor_renovacion'
    service.sessions.delete(sid, token)
    restarted = service.responder('¿Cuánto demora?')
    assert restarted['intencion'] == 'general' and not restarted['fuentes']
    assert len(graph_state(service, restarted['session_id'])['historial']) == 1
    assert not list(service.grafo.checkpointer.list({'configurable': {'thread_id': sid}}))


def test_contexto_estructurado_minimo_e_historial_limitado(motor_local):
    service, _ = motor_local
    first = service.responder('Quiero renovar el DNI de mi hijo de 10 años; caso ficticio.')
    sid, token = first['session_id'], first['session_token']
    for _ in range(8):
        service.responder('¿Y qué requisitos necesito?', sid, token)
    state = graph_state(service, sid)
    assert len(state['historial']) == 6
    assert state['contexto_solicitante'] == {'grupo_edad': 'menor', 'destinatario': 'descendiente'}
    assert '10' not in str(state['contexto_solicitante'])


@pytest.mark.parametrize('question', [
    '¿Debo llevar mi DNI vigente como padre?',
    'Soy adulto, ¿debo presentar mi DNI para acompañarlo?',
    '¿Las fotos deben ser tamaño pasaporte?',
])
def test_documentos_del_acompanante_no_cambian_titular(question):
    state = turn({}, 'Necesito renovar el DNI de mi hijo de 10 años.')
    state = turn(state, question)
    assert state['tramite_actual'] == 'dni_menor_renovacion'
    assert state['contexto_solicitante']['grupo_edad'] == 'menor'


def test_seguimiento_sin_contexto_dni_solicita_aclaracion():
    state = turn({}, '¿Dónde consulto el estado del trámite?')
    assert state['requiere_aclaracion'] and state['intencion'] == 'general'
    state = turn({}, '¿Dónde consulto el estado del trámite de DNI?')
    assert state['intencion'] == 'dni_consulta_estado'
    assert state['tramite_documentado']


def test_otro_titular_no_hereda_operacion_sin_pedirla():
    state = turn({}, 'Mi hijo menor necesita su primer DNI.')
    state = turn(state, 'Ahora quiero consultar el estado de mi DNI: soy adulto.')
    assert state['intencion'] == 'dni_consulta_estado'
    assert not state['operacion_dni']
    state = turn(state, '¿Y cuánto cuesta?')
    assert state['requiere_aclaracion']


def test_categorias_contradictorias_no_se_eligen_arbitrariamente():
    state = turn({}, 'Mi hijo menor de 25 años necesita renovar su DNI.')
    assert state['requiere_aclaracion'] and state['intencion'] == 'general'


@pytest.mark.parametrize('question,expected', [
    ('No es la primera vez: mi hijo menor ya tiene DNI.', 'dni_menor_renovacion'),
    ('No es una renovación; es el primer DNI de mi hijo menor.', 'dni_menor_primera_vez'),
    ('No soy adulto; soy menor y quiero renovar mi DNI.', 'dni_menor_renovacion'),
    ('¿Para la renovación del pasaporte debo presentar mi DNI?', 'fuera_alcance'),
])
def test_negaciones_con_articulos_y_objeto_solicitado(question, expected):
    assert turn({}, question)['intencion'] == expected


@pytest.mark.parametrize('question,expected', [
    ('Mi hijo menor necesita renovar DNI y debe acompañarlo su padre de 45 años.', 'dni_menor_renovacion'),
    ('Mi hijo necesita renovar DNI con el documento de su padre de 45 años.', 'general'),
])
def test_edad_del_acompanante_no_se_asigna_al_titular(question, expected):
    state = turn({}, question)
    assert state['intencion'] == expected
    assert state['contexto_solicitante']['grupo_edad'] != 'adulto'


@pytest.mark.parametrize('question,expected', [
    ('Quiero una visa y tengo mi DNI vigente.', 'fuera_alcance'),
    ('Necesito pasaporte para el primer DNI de mi hijo menor.', 'dni_menor_primera_vez'),
    ('Quiero consultar si llegó mi DNI.', 'dni_consulta_estado'),
])
def test_objetivo_y_documento_son_conceptos_distintos(question, expected):
    assert turn({}, question)['intencion'] == expected


def test_api_publica_preserva_contrato_y_secuencia(motor_local):
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        first = client.post('/api/v1/consultas', json={
            'pregunta': 'Quiero renovar el DNI de mi hijo de 10 años.',
        })
        assert first.status_code == 200
        sid, token = first.json()['session_id'], first.headers['X-Session-Token']
        for question in ('¿Cuánto demora?', '¿Y cuánto cuesta?', '¿Dónde solicito la cita?'):
            response = client.post('/api/v1/consultas', json={
                'pregunta': question, 'session_id': sid,
            }, headers={'X-Session-Token': token})
            assert response.status_code == 200
            assert response.json()['intencion'] == 'dni_menor_renovacion'
            assert response.json()['session_id'] == sid
            assert response.headers['X-Session-Token'] == token
        assert client.delete('/api/v1/sesiones/' + sid,
                             headers={'X-Session-Token': token}).status_code == 204
        fresh = client.post('/api/v1/consultas', json={'pregunta': '¿Cuánto cuesta?'})
        assert fresh.json()['intencion'] == 'general' and not fresh.json()['fuentes']
        assert fresh.json()['session_id'] != sid


@pytest.mark.parametrize('question,expected', [
    ('Mi hijo menor no necesita su primer DNI; ya tiene DNI vencido.', 'dni_menor_renovacion'),
    ('Mi hijo menor no quiere renovar; nunca tuvo DNI.', 'dni_menor_primera_vez'),
])
def test_negaciones_en_tercera_persona(question, expected):
    assert turn({}, question)['intencion'] == expected


@pytest.mark.parametrize('question,expected', [
    ('Tengo 17 años y quiero renovar mi DNI con un adulto.', 'dni_menor_renovacion'),
    ('Quiero renovar mi DNI con un adulto.', 'general'),
])
def test_acompanante_adulto_no_define_edad_propia(question, expected):
    state = turn({}, question)
    assert state['intencion'] == expected
    assert state['contexto_solicitante']['grupo_edad'] != 'adulto'


@pytest.mark.parametrize('question', ['Pasaporte', 'Necesito pasaporte'])
def test_mencion_sola_en_contexto_dni_no_cambia_procedimiento(question):
    state = turn({}, 'Quiero renovar el DNI de mi hijo menor.')
    state = turn(state, question)
    assert state['intencion'] == 'general' and state['requiere_aclaracion']
    assert state['tramite_actual'] == 'dni_menor_renovacion'


def test_titular_negado_no_gana_al_objetivo_afirmativo():
    state = turn({}, 'No quiero renovar el DNI de mi hijo menor; soy adulto y quiero renovar mi DNI.')
    assert state['tramite_actual'] == 'dni_adulto_renovacion'
    assert state['intencion'] == 'general' and not state['tramite_documentado']


def test_duplicado_identificado_no_habilita_nuevo_procedimiento(motor_local):
    service, calls = motor_local
    result = service.responder('Necesito un duplicado del DNI de mi hijo menor.')
    state = graph_state(service, result['session_id'])
    assert state['tramite_actual'] == 'dni_duplicado'
    assert state['estado_documental'] == 'no_documentado'
    assert not state['requiere_aclaracion'] and not state['tramite_documentado']
    assert not result['fuentes'] and not calls['retrieval'] and not calls['llm']
    assert 'no documenta' in result['respuesta'] and 'adulto' not in result['respuesta']


def test_duplicado_negado_no_impide_renovacion():
    state = turn({}, 'No quiero un duplicado de DNI; quiero renovar el DNI de mi hijo menor.')
    assert state['intencion'] == 'dni_menor_renovacion'


def test_solicitud_duplicado_sin_objeto_no_hereda_renovacion():
    state = turn({}, 'Quiero renovar el DNI de mi hijo menor.')
    state = turn(state, 'Ahora quiero un duplicado.')
    assert state['requiere_aclaracion'] and state['intencion'] == 'general'


@pytest.mark.parametrize('question', [
    '¿Puede acompañarlo mi hijo de 25 años?',
    '¿Mi hijo de 25 años puede acompañarlo?',
    '¿Puede ir mi hijo de 25 años como acompañante?',
    '¿Puede actuar mi hijo de 25 años como representante?',
    '¿Debo presentar el DNI de mi hijo de 25 años como documento de apoyo?',
])
def test_p2_personas_de_apoyo_no_sustituyen_titular(question):
    state = turn({}, 'Necesito el primer DNI de mi hijo de 10 años.')
    holder = state['contexto_solicitante'].copy()
    state = turn(state, question)
    assert state['contexto_solicitante'] == holder
    assert state['tramite_actual'] == 'dni_menor_primera_vez'
    state = turn(state, '¿Y cuánto cuesta?')
    assert state['intencion'] == 'dni_menor_primera_vez'
    assert state['tipo_consulta'] == 'coste'


def test_p2_completar_titular_conserva_operacion():
    state = turn({}, '¿Cuánto cuesta renovar el DNI?')
    assert state['motivo_aclaracion'] == 'edad'
    assert state['operacion_dni'] == 'renovacion'
    state = turn(state, 'Es para mi hijo de 10 años')
    assert state['intencion'] == 'dni_menor_renovacion'
    assert not state['requiere_aclaracion']
    state = turn(state, '¿Y cuánto cuesta?')
    assert state['intencion'] == 'dni_menor_renovacion'


@pytest.mark.parametrize('denial', [
    'No quiero un duplicado',
    'No es un duplicado',
    'No necesito el duplicado del DNI',
])
def test_p2_duplicado_rechazado_no_se_hereda(denial):
    state = turn({}, 'Necesito un duplicado del DNI de mi hijo menor.')
    state = turn(state, denial)
    assert not state['operacion_dni']
    assert state['motivo_aclaracion'] == 'operacion'
    state = turn(state, '¿Cuánto cuesta?')
    assert state['requiere_aclaracion'] and not state['operacion_dni']
    state = turn(state, 'Es su primer DNI')
    assert state['intencion'] == 'dni_menor_primera_vez'


@pytest.mark.parametrize('questions,expected', [
    ([
        'Necesito el primer DNI de mi hijo de 10 años.',
        '¿Puede acompañarlo mi hijo de 25 años?',
        '¿Y cuánto cuesta?',
    ], ['dni_menor_primera_vez'] * 3),
    ([
        '¿Cuánto cuesta renovar el DNI?',
        'Es para mi hijo de 10 años',
        '¿Y cuánto cuesta?',
    ], ['general', 'dni_menor_renovacion', 'dni_menor_renovacion']),
    ([
        'Necesito un duplicado del DNI de mi hijo menor.',
        'No quiero un duplicado',
        '¿Cuánto cuesta?',
        'Quiero renovar el DNI',
        '¿Y cuánto demora?',
    ], ['general', 'general', 'general', 'dni_menor_renovacion', 'dni_menor_renovacion']),
])
def test_p2_sesion_real_fuentes_y_aclaraciones(motor_local, questions, expected):
    service, calls = motor_local
    sid = token = None
    for question, intent in zip(questions, expected):
        before_llm = len(calls['llm'])
        result = service.responder(question, sid, token)
        if sid is not None:
            assert result['session_id'] == sid
            assert result['session_token'] == token
        sid, token = result['session_id'], result['session_token']
        assert result['intencion'] == intent
        if intent == 'general':
            assert not result['fuentes']
            assert len(calls['llm']) == before_llm
        else:
            assert {s['archivo'] for s in result['fuentes']} == {intent + '.txt'}
            assert calls['llm'][-1]
    assert graph_state(service, sid)['contexto_solicitante']['grupo_edad'] == 'menor'
    assert len(graph_state(service, sid)['historial']) == len(questions)


@pytest.mark.parametrize('question', [
    '¿Puede ir acompañado por mi hijo de 25 años?',
    '¿Mi hijo de 25 años puede ser representante legal?',
])
def test_p2_rol_de_apoyo_explicito_no_asigna_capacidad_legal(question):
    state = turn({}, 'Necesito el primer DNI de mi hijo menor.')
    state = turn(state, question)
    assert state['tramite_actual'] == 'dni_menor_primera_vez'
    assert state['contexto_solicitante']['grupo_edad'] == 'menor'
    # La clasificación solo conserva el titular: no almacena autorizaciones.
    assert set(state['contexto_solicitante']) == {'grupo_edad', 'destinatario'}


def test_p2_misma_pregunta_con_titular_y_acompanante():
    state = turn({}, 'Necesito el primer DNI de mi hijo de 10 años; '
                 '¿puede acompañarlo mi hijo de 25 años?')
    assert state['intencion'] == 'dni_menor_primera_vez'
    assert state['contexto_solicitante']['grupo_edad'] == 'menor'


def test_p2_titular_identificado_si_cambia_no_hereda_operacion():
    state = turn({}, 'Necesito el primer DNI de mi hijo menor.')
    state = turn(state, 'Ahora es para mí, soy adulto.')
    assert not state['operacion_dni']
    assert state['requiere_aclaracion']


@pytest.mark.parametrize('correction,intent', [
    ('No quiero un duplicado; quiero renovar el DNI', 'dni_menor_renovacion'),
    ('No quiero un duplicado; es su primer DNI', 'dni_menor_primera_vez'),
])
def test_p2_duplicado_rectificado_en_el_mismo_turno(correction, intent):
    state = turn({}, 'Necesito un duplicado del DNI de mi hijo menor.')
    state = turn(state, correction)
    assert state['intencion'] == intent
    assert not state['requiere_aclaracion']


def test_p2_aclaracion_llega_al_generador_con_pregunta_original(motor_local):
    service, calls = motor_local
    first = service.responder('¿Cuánto cuesta renovar el DNI?')
    result = service.responder('Es para mi hijo de 10 años',
                               first['session_id'], first['session_token'])
    assert result['intencion'] == 'dni_menor_renovacion'
    assert len(calls['llm']) == 1
    assert '¿Cuánto cuesta renovar el DNI?' in calls['llm'][0]
    assert 'Es para mi hijo de 10 años' in calls['llm'][0]
    assert 'dni_menor_renovacion' in calls['llm'][0]


@pytest.mark.parametrize('question,expected,group', [
    ('¿Debo presentar el DNI de mi hijo de 25 años para su renovación?', 'general', 'adulto'),
    ('¿Debo presentar el DNI de mi hijo de 10 años para su renovación?', 'dni_menor_renovacion', 'menor'),
    ('¿Puede acompañarlo mi hijo de 25 años?', 'dni_menor_renovacion', 'menor'),
    ('¿Debo presentar el DNI de mi hijo de 25 años como documento de apoyo?', 'dni_menor_renovacion', 'menor'),
    ('¿Debo presentar el DNI del padre como documento de apoyo?', 'dni_menor_renovacion', 'menor'),
    ('¿Debo presentar el DNI de la madre como documento de apoyo?', 'dni_menor_renovacion', 'menor'),
    ('¿Debo presentar el DNI del representante como documento de apoyo?', 'dni_menor_renovacion', 'menor'),
])
def test_p24_matriz_documento_titular_y_apoyo(question, expected, group):
    state = turn({}, 'Necesito renovar el DNI de mi hijo de 10 años')
    state = turn(state, question)
    assert state['intencion'] == expected
    assert state['contexto_solicitante']['grupo_edad'] == group
    assert not state['requiere_aclaracion']
    state = turn(state, '¿Cuánto cuesta?')
    assert state['contexto_solicitante']['grupo_edad'] == group
    assert state['operacion_dni'] == 'renovacion'
    if group == 'adulto':
        assert state['estado_documental'] == 'no_documentado'
    else:
        assert state['intencion'] == 'dni_menor_renovacion'


def test_p24_presentar_dni_del_titular_sin_contexto():
    state = turn({}, '¿Debo presentar el DNI de mi hijo de 10 años para su renovación?')
    assert state['intencion'] == 'dni_menor_renovacion'
    assert state['contexto_solicitante']['grupo_edad'] == 'menor'


@pytest.mark.parametrize('denial', [
    'No es DNI por primera vez',
    'No es el DNI por primera vez',
    'No es un DNI por primera vez',
    'No es la primera inscripción',
    'No es su primer DNI',
    'No quiero tramitar el DNI por primera vez',
])
def test_p25_negacion_ajena_a_operacion_activa_conserva_renovacion(denial):
    state = turn({}, 'Quiero renovar el DNI de mi hijo menor')
    state = turn(state, denial)
    assert state['operacion_dni'] == 'renovacion'
    assert state['intencion'] == 'dni_menor_renovacion'
    assert not state['requiere_aclaracion']
    state = turn(state, '¿Cuánto cuesta?')
    assert state['intencion'] == 'dni_menor_renovacion'
    state = turn(state, 'En realidad es su primer DNI')
    assert state['intencion'] == 'dni_menor_primera_vez'


@pytest.mark.parametrize('correction,expected', [
    ('No es DNI por primera vez; quiero renovar el DNI', 'dni_menor_renovacion'),
    ('No quiero renovar; es DNI por primera vez', 'dni_menor_primera_vez'),
    ('No es un duplicado; es DNI por primera vez', 'dni_menor_primera_vez'),
    ('No es DNI por primera vez; tampoco quiero renovar', 'general'),
])
def test_p25_rectificaciones_y_negaciones_multiples(correction, expected):
    state = turn({}, 'Quiero renovar el DNI de mi hijo menor')
    state = turn(state, correction)
    assert state['intencion'] == expected
    if expected == 'general':
        assert not state['operacion_dni'] and state['requiere_aclaracion']


def test_p25_negacion_del_procedimiento_activo_pide_aclaracion():
    state = turn({}, 'Quiero el primer DNI de mi hijo menor')
    state = turn(state, 'No es DNI por primera vez')
    assert not state['operacion_dni'] and state['requiere_aclaracion']
    state = turn(state, '¿Cuánto cuesta?')
    assert state['requiere_aclaracion']
    state = turn(state, 'Es una renovación')
    assert state['intencion'] == 'dni_menor_renovacion'


@pytest.mark.parametrize('question', [
    '¿Debo presentar el DNI de mi hijo de 25 años?',
    '¿Debo presentar el DNI de mi hijo de 25 años como documento de apoyo para su renovación?',
])
def test_p24_documento_con_finalidad_ambigua_pide_aclaracion(question):
    state = turn({}, 'Necesito renovar el DNI de mi hijo de 10 años')
    previous_holder = state['contexto_solicitante'].copy()
    state = turn(state, question)
    assert state['requiere_aclaracion']
    assert state['intencion'] == 'general'
    assert state['contexto_solicitante'] == previous_holder
    assert not state['operacion_dni']
    state = turn(state, '¿Cuánto cuesta?')
    assert state['requiere_aclaracion']
    state = turn(state, 'Quiero renovar el DNI de mi hijo adulto')
    assert state['tramite_actual'] == 'dni_adulto_renovacion'
    assert state['estado_documental'] == 'no_documentado'


@pytest.mark.parametrize('denial', ['No es DNI por primera vez', 'No es su primer DNI'])
def test_p25_negacion_sin_operacion_previa_no_infiere_renovacion(denial):
    state = turn({}, denial)
    assert state['requiere_aclaracion']
    assert not state['operacion_dni']


@pytest.mark.parametrize('questions,intents', [
    ([
        'Necesito renovar el DNI de mi hijo de 10 años',
        '¿Debo presentar el DNI de mi hijo de 25 años para su renovación?',
        '¿Cuánto cuesta?',
    ], ['dni_menor_renovacion', 'general', 'general']),
    ([
        'Necesito renovar el DNI de mi hijo de 10 años',
        '¿Debo presentar el DNI de mi hijo de 10 años para su renovación?',
        '¿Cuánto demora?', '¿Cuánto cuesta?', '¿Dónde solicito la cita?',
    ], ['dni_menor_renovacion'] * 5),
    ([
        'Mi hijo menor necesita su primer DNI',
        '¿Puede acompañarlo mi hijo de 25 años?', '¿Cuánto cuesta?',
    ], ['dni_menor_primera_vez'] * 3),
    ([
        'Quiero renovar el DNI de mi hijo menor',
        'No es DNI por primera vez', '¿Cuánto cuesta?',
    ], ['dni_menor_renovacion'] * 3),
    ([
        'Quiero el primer DNI de mi hijo menor',
        'No es DNI por primera vez', '¿Cuánto cuesta?',
        'Es una renovación', '¿Dónde solicito la cita?',
    ], ['dni_menor_primera_vez', 'general', 'general',
        'dni_menor_renovacion', 'dni_menor_renovacion']),
])
def test_p24_p25_matriz_grafo_sesion_y_fuentes(motor_local, questions, intents):
    service, calls = motor_local
    sid = token = None
    for question, intent in zip(questions, intents):
        previous_calls = len(calls['llm'])
        result = service.responder(question, sid, token)
        if sid:
            assert result['session_id'] == sid and result['session_token'] == token
        sid, token = result['session_id'], result['session_token']
        assert result['intencion'] == intent
        if intent == 'general':
            assert not result['fuentes']
            assert len(calls['llm']) == previous_calls
        else:
            assert {s['archivo'] for s in result['fuentes']} == {intent + '.txt'}
        # Una conversación independiente no hereda ninguna de estas operaciones.
    other = service.responder('¿Cuánto cuesta?')
    assert other['session_id'] != sid
    assert other['intencion'] == 'general' and not other['fuentes']
    assert not graph_state(service, other['session_id'])['operacion_dni']
