"""Regresiones estructurales: evidencia del turno, transición y puertas RAG."""
import pytest

from app.graph.classification import clasificar


def turn(state, question):
    return clasificar({**state, 'pregunta': question})


def test_edad_heredada_no_resuelve_contradiccion():
    state = turn({}, 'Necesito renovar el DNI de mi hijo de 10 años')
    state = turn(state, 'Mi hijo es menor de 25 años')
    assert state['requiere_aclaracion']
    state = turn(state, 'Es para mi hijo')
    assert state['requiere_aclaracion']
    assert state['motivo_aclaracion'] == 'edad'
    assert state['intencion'] == 'general'


def test_rechazo_no_desaparece_al_aclarar_documento():
    state = turn({}, 'Necesito renovar el DNI de mi hijo de 10 años')
    state = turn(state, 'No quiero renovar. ¿Debo presentar el DNI de mi hijo de 25 años?')
    assert state['requiere_aclaracion'] and not state['operacion_dni']
    state = turn(state, 'Es un documento de apoyo')
    assert state['requiere_aclaracion'] and not state['operacion_dni']
    assert state['intencion'] == 'general'


from copy import deepcopy
from itertools import product

from app.graph.classification import extraer_evidencia
from app.graph.context_policy import (
    contexto_inicial, ruta_documental, transicionar, validar_contexto,
)
from app.graph.state import EvidenciaTurno as E


@pytest.mark.parametrize('answer,resolved,group', [
    ('Mi hijo tiene 25 años', True, 'adulto'),
    ('Mi hijo es menor de 25 años', False, ''),
    ('Es para mi hijo', False, ''),
    ('Es para mi hijo de 10 años', True, 'menor'),
    ('Es para mi hijo adulto', True, 'adulto'),
])
def test_cinco_aclaraciones_de_edad_no_equivalentes(answer, resolved, group):
    s = turn({}, 'Necesito renovar el DNI de mi hijo de 10 años')
    s = turn(s, 'Mi hijo es menor de 25 años')
    source = deepcopy(s['contexto_canonico']['edad'])
    s = turn(s, answer)
    c = s['contexto_canonico']
    assert validar_contexto(c)
    assert s['requiere_aclaracion'] != resolved
    if resolved:
        assert c['edad']['estado'] == 'confirmado'
        assert c['edad']['valor'] == group and c['edad']['turno'] == 3
        assert c['edad']['origen'] == 'explicito'
        assert s['operacion_dni'] == 'renovacion'
        assert ruta_documental(c) == ('dni_menor_renovacion' if group == 'menor' else '')
    else:
        assert c['edad'] == source and not ruta_documental(c)


def test_cambio_de_edad_factual_requiere_confirmacion_y_limite_no_es_edad():
    e = extraer_evidencia('Mi hijo es menor de 25 años')
    assert not e.edad and 'edad' in e.dudas
    s = turn({}, 'Necesito renovar el DNI de mi hijo de 10 años')
    s = turn(s, 'Mi hijo tiene 25 años')
    assert s['requiere_aclaracion'] and s['contexto_canonico']['edad']['estado'] == 'conflicto'
    s = turn(s, 'Es para mi hijo')
    assert s['requiere_aclaracion']
    s = turn(s, 'Es para mi hijo adulto')
    assert s['tramite_actual'] == 'dni_adulto_renovacion'
    assert s['estado_documental'] == 'no_documentado'


def base():
    return transicionar(None, E(dni=True, titular='descendiente', edad='menor', operacion='renovacion'))


@pytest.mark.parametrize('op,topic', list(product(
    ['primera_vez', 'renovacion', 'duplicado'], ['coste', 'plazo', 'requisitos', 'cita'])))
def test_rechazos_persisten_independientes_del_tema_y_de_otros_datos(op, topic):
    c = transicionar(None, E(dni=True, titular='descendiente', edad='menor', operacion=op))
    c = transicionar(c, E(rechazadas=(op,), dudas=('documento',)))
    for evidence in (E(tema=topic, pregunta_tema=True), E(edad='menor'), E(funcion_documento='apoyo')):
        c = transicionar(c, evidence)
        assert op in c['rechazadas']
        assert c['operacion']['valor'] == ''
        assert not ruta_documental(c)
    # Una observación no levanta el rechazo.
    c = transicionar(c, E(operacion=op, observacion=True))
    assert op in c['rechazadas'] and not ruta_documental(c)
    c = transicionar(c, E(operacion=op))
    assert op not in c['rechazadas'] and c['operacion']['valor'] == op
    assert not c['pendientes'] and c['tema'] == topic
    assert ruta_documental(c) == (f'dni_menor_{op}' if op != 'duplicado' else '')


@pytest.mark.parametrize('reason,partial', [
    ('edad', E(titular='descendiente')),
    ('operacion', E(edad='menor')),
    ('dni_previo', E(titular='descendiente', edad='menor')),
    ('documento', E(operacion='renovacion')),
])
def test_una_dimension_no_confirma_otra(reason, partial):
    c = base()
    if reason == 'dni_previo':
        c = transicionar(c, E(operacion='primera_vez', observacion=True))
    else:
        c = transicionar(c, E(dudas=(reason,)))
    assert reason in c['pendientes']
    c = transicionar(c, partial)
    assert reason in c['pendientes'] and not ruta_documental(c)


@pytest.mark.parametrize('order', [
    [E(operacion='renovacion'), E(funcion_documento='apoyo')],
    [E(funcion_documento='apoyo'), E(operacion='renovacion')],
])
def test_aclaraciones_independientes_en_orden_alternativo(order):
    c = transicionar(base(), E(dudas=('operacion', 'documento')))
    c = transicionar(c, order[0])
    assert c['pendientes'] and not ruta_documental(c)
    c = transicionar(c, order[1])
    assert not c['pendientes'] and ruta_documental(c) == 'dni_menor_renovacion'


def test_transicion_pura_procedencia_y_completar_vs_sustituir():
    c = transicionar(None, E(dni=True, operacion='renovacion', tema='coste', pregunta_tema=True))
    frozen = deepcopy(c)
    filled = transicionar(c, E(titular='descendiente', edad='menor'))
    assert c == frozen
    assert filled['revision'] == c['revision']
    assert filled['operacion'] == c['operacion']
    assert filled['retomar'] == 'coste'
    inherited = transicionar(filled, E(tema='plazo', pregunta_tema=True))
    assert inherited['edad'] == filled['edad']
    changed = transicionar(inherited, E(titular='propio', edad='adulto'))
    assert changed['revision'] > inherited['revision']
    assert not changed['operacion']['valor'] and 'operacion' in changed['pendientes']
    assert not ruta_documental(changed)
    assert all(changed[f]['revision'] == changed['revision'] for f in ('titular', 'edad', 'operacion'))


def test_seleccion_entre_varios_no_hereda_edad_del_titular_anterior():
    c = transicionar(base(), E(dudas=('titular',), operacion='renovacion'))
    assert c['titular']['estado'] == 'conflicto' and c['edad']['valor'] == ''
    c = transicionar(c, E(operacion='renovacion'))
    assert 'titular' in c['pendientes'] and not ruta_documental(c)
    c = transicionar(c, E(titular='descendiente'))
    assert 'titular' not in c['pendientes'] and 'edad' in c['pendientes']
    c = transicionar(c, E(edad='adulto'))
    assert not c['pendientes'] and c['edad']['valor'] == 'adulto'
    assert c['operacion']['valor'] == 'renovacion' and not ruta_documental(c)


@pytest.mark.parametrize('mutation', ['revision', 'turno', 'origen', 'rechazada', 'edad', 'motivo', 'valor'])
def test_contextos_inconsistentes_no_autorizan_documentos(mutation):
    c = base()
    if mutation == 'revision':
        c['edad']['revision'] += 1
    elif mutation == 'turno':
        c['operacion']['turno'] += 10
    elif mutation == 'origen':
        c['edad']['origen'] = 'ausente'
    elif mutation == 'rechazada':
        c['rechazadas'] = ['renovacion']
    elif mutation == 'edad':
        c['edad']['estado'] = 'conflicto'
    elif mutation == 'motivo':
        c['pendientes'] = {'inventado': 'faltante'}
    else:
        c['edad']['valor'] = 'inventado'
    assert not validar_contexto(c) and not ruta_documental(c)
    with pytest.raises(ValueError, match='inválido'):
        transicionar(c, E())


def test_no_se_migran_hechos_desde_etiquetas_ni_historial():
    s = clasificar({'pregunta': '¿Cuánto cuesta?', 'tramite_actual': 'dni_menor_renovacion',
                   'operacion_dni': 'renovacion', 'contexto_solicitante': {'grupo_edad': 'menor'},
                   'historial': [{'pregunta': 'Quiero renovar el DNI de mi hijo menor'}]})
    assert s['requiere_aclaracion'] and s['motivo_aclaracion'] == 'tramite'
    assert not s['contexto_canonico']['operacion']['valor']
    c = transicionar(base(), E(rechazadas=('renovacion',)))
    s = clasificar({'contexto_canonico': c, 'pregunta': 'Es para mi hijo menor',
                   'tramite_actual': 'dni_menor_renovacion', 'operacion_dni': 'renovacion'})
    assert not s['operacion_dni'] and s['requiere_aclaracion']


@pytest.fixture
def motor(monkeypatch, entorno_aislado):
    from pathlib import Path
    from app.graph import dni_graph
    from unittest.mock import Mock
    documents = [{'contenido': path.read_text(encoding='utf-8'), 'score': 0.1,
                  'metadata': {'archivo': path.name, 'chunk': 0}}
                 for path in Path('data/raw').glob('*.txt')]
    retrieve = Mock(return_value=documents)
    provider = Mock(return_value='Respuesta simulada para comprobar las transiciones.')
    class LocalLLM:
        generar_respuesta = staticmethod(provider)
    monkeypatch.setattr(dni_graph, 'recuperar_contexto', retrieve)
    monkeypatch.setattr(dni_graph, 'LLMService', LocalLLM)
    return entorno_aislado, retrieve, provider


def snapshot(service, sid):
    return service.grafo.get_state({'configurable': {'thread_id': sid}}).values


@pytest.mark.parametrize('kind', ['edad', 'rechazo'])
def test_defectos_corregidos_en_grafo_sin_recuperacion_ni_generacion(kind, motor):
    service, retrieve, provider = motor
    first = service.responder('Necesito renovar el DNI de mi hijo de 10 años')
    sid, token = first['session_id'], first['session_token']
    before = retrieve.call_count, provider.call_count
    questions = (['Mi hijo es menor de 25 años', 'Es para mi hijo'] if kind == 'edad' else
                 ['No quiero renovar. ¿Debo presentar el DNI de mi hijo de 25 años?', 'Es un documento de apoyo'])
    for q in questions:
        result = service.responder(q, sid, token)
        assert result['session_id'] == sid and result['session_token'] == token
        assert result['intencion'] == 'general' and not result['fuentes']
        assert snapshot(service, sid)['requiere_aclaracion']
        assert (retrieve.call_count, provider.call_count) == before
    confirmation = 'Es para mi hijo de 10 años' if kind == 'edad' else 'Quiero renovar el DNI'
    result = service.responder(confirmation, sid, token)
    assert result['intencion'] == 'dni_menor_renovacion'
    assert {s['archivo'] for s in result['fuentes']} == {'dni_menor_renovacion.txt'}
    assert not snapshot(service, sid)['requiere_aclaracion']


@pytest.mark.parametrize('damage', ['sin_canonico', 'pendiente', 'revision', 'propuesta'])
def test_puerta_documental_no_confia_en_flags_o_rutas_legadas(damage, motor):
    from app.graph import dni_graph
    _, retrieve, provider = motor
    c = base()
    if damage == 'sin_canonico':
        c = None
    elif damage == 'pendiente':
        c = transicionar(c, E(dudas=('edad',)))
    elif damage == 'revision':
        c['edad']['revision'] += 1
    else:
        c['propuesta_operacion'] = 'primera_vez'
    stale = {'contexto_canonico': c, 'pregunta': '¿Cuánto cuesta?',
             'intencion': 'dni_menor_renovacion', 'requiere_aclaracion': False,
             'pregunta_busqueda': 'no debe consultarse', 'contexto': 'dato anterior',
             'estado_documental': 'disponible', 'fuentes': [{'archivo': 'anterior.txt'}]}
    for direct in [False, True]:
        state = dni_graph.recuperar_documentos(stale) if not direct else stale
        drafted = dni_graph.redactar_respuesta_minimizada(state)
        assert drafted['intencion'] == 'general'
        assert 'Para poder orientarle' in drafted['respuesta_borrador']
        assert not retrieve.called and not provider.called
        if not direct:
            assert not state['fuentes'] and not state['contexto']


@pytest.mark.parametrize('delete', [False, True])
def test_contexto_canonico_rechazos_se_eliminan_con_sesion(delete, motor):
    from app.services.session_service import SesionNoAutorizada
    service, _, _ = motor
    now = [0.0]
    service.sessions.clock = lambda: now[0]
    service.sessions.ttl = 10
    first = service.responder('Necesito renovar el DNI de mi hijo menor')
    sid, token = first['session_id'], first['session_token']
    service.responder('No quiero renovar', sid, token)
    assert snapshot(service, sid)['contexto_canonico']['rechazadas'] == ['renovacion']
    other = service.responder('¿Cuánto cuesta?')
    assert not snapshot(service, other['session_id'])['contexto_canonico']['rechazadas']
    if delete:
        service.sessions.delete(sid, token)
    else:
        now[0] = 11
        service.sessions.cleanup()
    assert not list(service.grafo.checkpointer.list({'configurable': {'thread_id': sid}}))
    with pytest.raises(SesionNoAutorizada):
        service.responder('Quiero renovar', sid, token)
    fresh = service.responder('Necesito el primer DNI de mi hijo menor')
    assert fresh['intencion'] == 'dni_menor_primera_vez'
    assert not snapshot(service, fresh['session_id'])['contexto_canonico']['rechazadas']


def test_propuesta_rechazada_y_flags_inconsistentes_no_autorizan():
    c = base()
    c['rechazadas'] = ['primera_vez']
    c['propuesta_operacion'] = 'primera_vez'
    assert not validar_contexto(c) and not ruta_documental(c)
    c = base()
    c['pendientes'] = {'edad': 'faltante'}
    c['retomar'] = 'coste'
    assert not validar_contexto(c) and not ruta_documental(c)


def test_duda_de_edad_no_es_permiso_para_confirmar_procedimiento_incompatible():
    c = transicionar(None, E(dni=True, operacion='primera_vez', titular='descendiente'))
    assert set(c['pendientes']) == {'edad'}
    c = transicionar(c, E(operacion='renovacion', observacion=True))
    assert {'edad', 'dni_previo'} <= c['pendientes'].keys()
    assert c['operacion']['estado'] == 'conflicto'
    c = transicionar(c, E(edad='menor'))
    assert 'edad' not in c['pendientes'] and 'dni_previo' in c['pendientes']
    assert not ruta_documental(c)
    c = transicionar(c, E(operacion='renovacion', observacion=True))
    assert ruta_documental(c) == 'dni_menor_renovacion'


def test_observacion_de_alternativa_rechazada_no_lanza_ni_autoriza():
    c = transicionar(base(), E(rechazadas=('primera_vez',)))
    c = transicionar(c, E(operacion='primera_vez', observacion=True))
    assert validar_contexto(c) and not ruta_documental(c)
    assert c['rechazadas'] == ['primera_vez']
    assert c['propuesta_operacion'] != 'primera_vez'
    assert 'dni_previo' in c['pendientes']
    c = transicionar(c, E(operacion='primera_vez'))
    assert not c['rechazadas'] and ruta_documental(c) == 'dni_menor_primera_vez'


def test_negar_otra_operacion_o_marcar_tema_no_resuelve_contradiccion():
    for evidence in [E(operacion='primera_vez', observacion=True, rechazadas=('duplicado',)),
                     E(operacion='primera_vez', observacion=True, cambio=True)]:
        c = transicionar(base(), evidence)
        assert 'dni_previo' in c['pendientes'] and not ruta_documental(c)


def test_matriz_acotada_de_transiciones_categoricas():
    events = [
        E(), E(dni=True, titular='descendiente', edad='menor', operacion='renovacion'),
        E(dni=True, titular='propio', edad='adulto', operacion='primera_vez'),
        E(rechazadas=('renovacion',), dudas=('documento',)), E(edad='adulto'),
        E(dudas=('edad',)), E(dudas=('titular',), operacion='renovacion'),
        E(dudas=('operacion',)), E(operacion='primera_vez', observacion=True),
        E(funcion_documento='apoyo'), E(funcion_documento='titular'), E(abandonar=True),
        E(otro_tramite=True), E(tema='seguimiento', cambio=True, dni=True),
        E(operacion='duplicado'), E(tema='coste', pregunta_tema=True),
    ]
    # 256 pares, partiendo de contexto confirmado. No es una prueba de lenguaje.
    for i, first in enumerate(events):
        for j, second in enumerate(events):
            c = transicionar(transicionar(base(), first), second)
            assert validar_contexto(c), (i, j)
            if c['pendientes']:
                assert not ruta_documental(c), (i, j)
            assert c['operacion']['valor'] not in c['rechazadas'], (i, j)
