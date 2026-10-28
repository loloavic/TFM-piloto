"""Fase B: disposiciones comunes confirmadas, sin sustituir reglas particulares."""
import pytest
from tests.test_adult_dni import motor, snapshot
from app.graph import dni_graph

PROCEDURES=[
    ('Soy adulto y quiero renovar mi DNI','dni_mayor_renovacion.txt'),
    ('Soy adulto y quiero rectificar los nombres de mi DNI','dni_mayor_rectificacion.txt'),
    ('Soy adulto y quiero cambiar el estado civil de mi DNI','dni_mayor_estado_civil.txt'),
]


@pytest.mark.parametrize('start,file',PROCEDURES)
@pytest.mark.parametrize('query,rule,expected',[
    ('¿Cuánto demora?','plazo','3 a 4 meses'),
    ('¿Cómo hago seguimiento?','seguimiento','https://serviciosportal.reniec.gob.pe/cetdnipi/inicio.htm'),
    ('¿Qué advertencias debo tener en cuenta?','advertencias','sin cita previa'),
])
def test_reglas_comunes_por_modalidad_sin_exigir_condiciones_civiles(start,file,query,rule,expected,motor):
    service,_,prompts=motor
    first=service.responder(start + '. ' + query)
    assert {f['archivo'] for f in first['fuentes']} == {file}
    assert {f['regla'] for f in first['fuentes']} == {rule}
    assert expected in first['respuesta'] and not prompts
    assert not snapshot(service,first['session_id'])['requiere_aclaracion']
    assert '€7' not in first['respuesta'] and 'partida de nacimiento' not in first['respuesta']
    if rule == 'plazo':
        assert 'referencial' in first['respuesta'] and 'no significa' in first['respuesta']
    if rule == 'seguimiento':
        assert '100 %' in first['respuesta'] and 'no constituye' in first['respuesta']
        assert 'nunca en el asistente' in first['respuesta']


def test_general_no_suple_requisitos_civiles_ni_repite_advertencias(motor):
    service,_,_=motor
    first=service.responder('Soy adulto y quiero cambiar el estado civil en mi DNI. ¿Cuánto demora?')
    sid,token=first['session_id'],first['session_token']
    assert '3 a 4 meses' in first['respuesta'] and 'sin cita previa' not in first['respuesta']
    r=service.responder('¿Qué documentos debo presentar?',sid,token)
    assert not r['fuentes']
    assert snapshot(service,sid)['motivo_aclaracion'] == 'adulto_transicion'


def test_reglas_generales_no_suplen_regla_especifica_ausente(motor):
    service,retrieve,prompts=motor
    retrieve.return_value=[d for d in retrieve.return_value if d['contenido'].startswith('[[REGLA:plazo]]')]
    r=service.responder('Soy adulto y quiero rectificar nombres en mi DNI')
    assert not r['fuentes'] and not prompts
    assert r['verificacion'].startswith('abstencion_documental:')


def test_plazo_comun_de_combinacion_no_autoriza_tasas(motor):
    service,_,_=motor
    first=service.responder('Soy adulto y quiero renovar mi DNI y cambiar mi estado civil. ¿Cuánto demora?')
    sid,token=first['session_id'],first['session_token']
    assert '3 a 4 meses' in first['respuesta']
    assert {f['regla'] for f in first['fuentes']} == {'plazo'}
    r=service.responder('¿Cuánto cuesta?',sid,token)
    assert not r['fuentes'] and 'no está confirmada' in r['respuesta']


def test_verificador_no_permite_garantia_de_entrega_al_100(motor):
    service,_,_=motor
    first=service.responder('Soy adulto y quiero renovar mi DNI. ¿Cómo hago seguimiento?')
    s=snapshot(service,first['session_id'])
    r=dni_graph.verificar_respuesta({**s,'respuesta_borrador':'Al 100 % el DNI está disponible: puede recogerlo sin consultar.'})
    assert r['verificacion'].startswith('observada:')
    assert 'no constituye' in r['respuesta_final']


def test_plazo_combinado_exige_reglas_comunes_coherentes(motor):
    service,_,_=motor
    first=service.responder('Soy adulto y quiero rectificar nombres en mi DNI vencido. ¿Cuánto demora?')
    assert {f['regla'] for f in first['fuentes']} == {'plazo'}
    assert {f['archivo'] for f in first['fuentes']} == {'dni_mayor_renovacion.txt','dni_mayor_rectificacion.txt'}
    s=snapshot(service,first['session_id'])
    s['fragmentos'][0]['contenido']='Plazo alternativo no confirmado'
    r=dni_graph.verificar_respuesta({**s,'respuesta_borrador':'3 a 4 meses siempre'})
    assert 'versiones incompatibles' in r['respuesta_final'] and r['verificacion'].startswith('observada:')

    drafted=dni_graph.redactar_respuesta(s)
    verified=dni_graph.verificar_respuesta(drafted)
    assert verified['verificacion'].startswith('abstencion_documental:')
