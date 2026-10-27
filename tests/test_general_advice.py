"""Tema de recomendaciones generales; intención y autorización se conservan."""
import pytest
from tests.test_adult_dni import motor,snapshot
from tests.test_widow_answers import PENDING
from app.graph.classification import normalizar,tipo_consulta

RECOMMENDATIONS=[
    '¿Qué recomendaciones debo tener en cuenta antes de acudir al Consulado para realizar mi trámite de DNI?',
    '¿Qué recomendaciones debo tener en cuenta?',
    '¿Qué debo tener en cuenta antes de acudir al Consulado?',
    '¿Qué precauciones debo tomar para mi cita?',
    '¿Qué debo revisar antes de ir al trámite?',
    '¿Hay alguna recomendación antes de acudir?',
]


@pytest.mark.parametrize('question',RECOMMENDATIONS)
def test_advertencias_multivuelta_no_repite_requisitos_de_viudez(question,motor):
    service,_,prompts=motor
    first=service.responder(PENDING+' Mi esposo era italiano')
    sid,token=first['session_id'],first['session_token']
    before=snapshot(service,sid)['contexto_canonico']
    calls=len(prompts)
    r=service.responder(question,sid,token)
    c=snapshot(service,sid)['contexto_canonico']
    assert c['tema']=='advertencias'
    for field in ['edad','operacion','condiciones_adulto','revision']:
        assert c[field]==before[field]
    assert c['titular']['valor']==before['titular']['valor']
    assert c['titular']['estado']==before['titular']['estado']
    assert r['intencion']=='dni_adulto_rectificacion'
    assert {f['archivo'] for f in r['fuentes']}=={'dni_mayor_estado_civil.txt'}
    assert {f['regla'] for f in r['fuentes']}=={'advertencias'}
    assert 'sin cita previa' in r['respuesta']
    assert 'requisitos estén vigentes' in r['respuesta']
    assert 'Cuando el procedimiento exija fotografías' in r['respuesta']
    assert 'acta' not in r['respuesta'].lower() and len(prompts)==calls


@pytest.mark.parametrize('question,expected',[
    ('¿Qué recomendaciones hay sobre el coste?', 'coste'),
    ('¿Cuánto cuesta y qué recomendaciones hay para mi cita?', 'coste'),
    ('¿Qué recomendaciones hay sobre las fotografías?', 'fotografias'),
    ('¿Qué documentos debo revisar antes de ir al trámite?', 'requisitos'),
    ('¿Qué requisitos debo tener en cuenta antes de acudir?', 'requisitos'),
    ('¿Qué recomendaciones hay para reservar cita?', 'cita'),
    ('¿Dónde solicito cita y qué recomendaciones debo seguir?', 'cita'),
    ('¿Qué precauciones para mi cita?', 'advertencias'),
    ('¿Qué recomendaciones hay para verificar la vigencia de los requisitos antes de ir?', 'advertencias'),
    ('No quiero recomendaciones; ¿cuánto cuesta?', 'coste'),
    ('No necesito advertencias, sino saber qué documentos debo presentar', 'requisitos'),
    ('No quiero recomendaciones. ¿Dónde solicito la cita?', 'cita'),
    ('No quiero recomendaciones', 'otra'),
    ('¿Qué debo tener en cuenta?', 'otra'),
])
def test_prioridades_negaciones_y_ambiguedad(question,expected):
    assert tipo_consulta(normalizar(question))==expected


def test_ausencia_de_regla_no_reemplaza_por_requisitos(motor,monkeypatch):
    from app.graph import dni_graph
    service,retrieve,prompts=motor
    first=service.responder(PENDING+' Mi esposo era italiano')
    retrieve.return_value=[d for d in retrieve.return_value if not d['contenido'].startswith('[[REGLA:advertencias]]')]
    monkeypatch.setattr(dni_graph,'recuperar_reglas_exactas',lambda *args:[])
    before=len(prompts)
    r=service.responder(RECOMMENDATIONS[0],first['session_id'],first['session_token'])
    s=snapshot(service,first['session_id'])
    assert s['contexto_canonico']['tema']=='advertencias'
    assert s['reglas_faltantes']==['dni_mayor_estado_civil.txt#advertencias']
    assert not r['fuentes'] and len(prompts)==before
    assert r['verificacion'].startswith('abstencion_documental:')


def test_volver_a_requisitos_y_otra_sesion_no_heredan_tema(motor):
    service,_,_=motor
    first=service.responder(PENDING+' Mi esposo era italiano')
    sid,token=first['session_id'],first['session_token']
    service.responder(RECOMMENDATIONS[0],sid,token)
    r=service.responder('¿Qué documentos debo presentar?',sid,token)
    assert {f['regla'] for f in r['fuentes']}=={'general','viudez_italia','italiano'}
    fresh=service.responder(RECOMMENDATIONS[0])
    assert not fresh['fuentes'] and fresh['session_id']!=sid
    assert not snapshot(service,fresh['session_id'])['contexto_canonico']['condiciones_adulto']
