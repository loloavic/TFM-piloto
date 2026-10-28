"""Confirmación operativa del 27-10-2026, sin proveedor externo."""
import pytest
from tests.test_adult_dni import motor
from tests.test_widow_answers import PENDING

@pytest.mark.parametrize('surname', [' No quiero recuperar el apellido materno.', ' Quiero recuperar el apellido materno.'])
def test_sustitucion_italiana_confirmada(surname, motor):
    service, _, prompts = motor
    r = service.responder(PENDING.replace('No quiero recuperar el apellido materno.', '') +
                          ' Mi esposo era italiano.' + surname)
    assert 'acta de defunción plurilingüe' in r['respuesta']
    assert 'sustituye' in r['respuesta']
    assert 'OBSERVACIÓN PENDIENTE' not in r['respuesta']
    assert 'No necesita presentar una certificación consular de defunción' in r['respuesta']
    assert not prompts

@pytest.mark.parametrize('topic,rule', [('¿Cuánto cuesta?', 'general'),
    ('¿Dónde solicito cita?', 'general'), ('¿Cuánto demora?', 'plazo'),
    ('¿Cómo consulto el estado de mi DNI?', 'seguimiento')])
def test_repreguntas_conservan_alcance(topic, rule, motor):
    service, _, _ = motor
    first = service.responder(PENDING + ' Mi esposo era italiano.')
    r = service.responder(topic, first['session_id'], first['session_token'])
    assert {f['regla'] for f in r['fuentes']} == {rule}
    assert 'OBSERVACIÓN PENDIENTE' not in r['respuesta']


def test_correccion_nacionalidad_no_extrapola(motor):
    service, _, _ = motor
    first = service.responder(PENDING + ' Mi esposo era italiano.')
    r = service.responder('Me equivoqué, no era italiano', first['session_id'], first['session_token'])
    assert 'No puedo confirmar' in r['respuesta']
    assert 'italiano' not in {f['regla'] for f in r['fuentes']}
    r = service.responder('¿Qué documentos debo presentar?', first['session_id'], first['session_token'])
    assert 'No necesita presentar una certificación consular' not in r['respuesta']


def test_nacionalidad_desconocida_no_sustituye(motor):
    service, _, _ = motor
    r = service.responder(PENDING)
    assert not r['fuentes']
    assert 'italiano' in r['respuesta']


def test_otro_pais_no_sustituye(motor):
    service, _, _ = motor
    r = service.responder(PENDING.replace('Italia', 'otro país') + ' Mi esposo era italiano.')
    assert 'viudez_otro' in {f['regla'] for f in r['fuentes']}
    assert 'italiano' not in {f['regla'] for f in r['fuentes']}
    assert 'No puedo confirmar' in r['respuesta']


def test_guardia_reemplaza_borrador_no_autorizado(motor):
    from app.graph.dni_graph import verificar_respuesta
    from tests.test_adult_dni import snapshot
    service, _, _ = motor
    r = service.responder(PENDING + ' Mi esposo era italiano.')
    state = snapshot(service, r['session_id'])
    result = verificar_respuesta({**state, 'respuesta_borrador': 'Debe presentar también el certificado consular de defunción.'})
    assert 'No necesita presentar una certificación consular de defunción' in result['respuesta_final']
    assert result['verificacion'] != 'ok'

@pytest.mark.parametrize('marriage', [
    'Mi matrimonio está registrado en Perú.',
    'Mi matrimonio está registrado en una oficina consular peruana.',
])
def test_matrimonio_independiente_y_condicional(marriage, motor):
    service, _, _ = motor
    r = service.responder(PENDING + ' Mi esposo era italiano. ' + marriage)
    assert 'si está registrado en Perú' in r['respuesta']
    assert 'si está registrado en una oficina consular peruana' in r['respuesta']
    assert 'No necesita presentar una certificación consular de defunción' in r['respuesta']


def test_peruano_registrado_consular_no_recibe_exencion_italiana(motor):
    service, _, _ = motor
    r = service.responder(PENDING + ' Mi esposo no era italiano, era peruano. '
                          'Su fallecimiento está registrado en una oficina consular peruana.')
    assert 'No puedo confirmar' in r['respuesta']
    assert 'italiano' not in {f['regla'] for f in r['fuentes']}
    assert 'No necesita presentar una certificación consular' not in r['respuesta']
