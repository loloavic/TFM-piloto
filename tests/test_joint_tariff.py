"""No acumulación confirmada, sin deducir tarifa conjunta."""
import pytest
from tests.test_adult_dni import motor, snapshot
from app.graph.adult_context import plan

BASE='Soy adulto y quiero rectificar mi fecha de nacimiento en el DNI vencido.'

@pytest.mark.parametrize('query',['¿Cuánto cuesta?', '¿Debo pagar 7 € o 14 €?',
                                 '¿Qué requisitos debo presentar y cuánto cuesta?'])
def test_no_acumulacion_explicita(query,motor):
    service,_,_=motor
    r=service.responder(BASE+' '+query)
    assert 'no son acumulables' in r['respuesta']
    assert 'ni si las tasas se acumulan' not in r['respuesta']
    assert 'No puedo confirmar el importe total' in r['respuesta']
    assert '€7' in r['respuesta'] and '14' not in r['respuesta']


def test_plan_exige_regla_tarifaria(motor):
    service,_,_=motor
    r=service.responder(BASE+' ¿Cuánto cuesta?')
    c=snapshot(service,r['session_id'])['contexto_canonico']
    assert 'no_acumulacion' in plan(c)['dni_mayor_renovacion.txt']

@pytest.mark.parametrize('validity,combined',[
    ('está vencido',True), ('vence en 59 días',True), ('vence en 60 días',True), ('vence en 61 días',False)])
def test_regla_se_limita_a_vigencia_procedente(validity,combined,motor):
    service,_,_=motor
    r=service.responder('Soy adulto y quiero rectificar mi fecha de nacimiento en el DNI. Mi DNI '+validity+'. ¿Cuánto cuesta?')
    rules={(f['archivo'],f['regla']) for f in r['fuentes']}
    assert (('dni_mayor_renovacion.txt','no_acumulacion') in rules)==combined
    assert ('no son acumulables' in r['respuesta'])==combined


def test_renovacion_con_rectificacion_y_repreguntas(motor):
    service,_,prompts=motor
    first=service.responder('Soy adulto y quiero renovar mi DNI vencido y rectificar mi fecha de nacimiento. ¿Qué documentos debo presentar y cuánto cuesta?')
    for q in ['¿Debo pagar 7 € o 14 €?', '¿Las tasas se acumulan?', '¿Qué requisitos debo presentar?']:
        r=service.responder(q,first['session_id'],first['session_token'])
        assert 'no son acumulables' in r['respuesta']
        assert 'Confirme con el Consulado qué importe' in r['respuesta']
        assert '14' not in r['respuesta']
        assert not prompts
    for fact in ['partida de nacimiento original apostillada','12 meses','copia certificada']:
        assert fact in first['respuesta']


def test_vigencia_desconocida_no_autoriza_regla(motor):
    service,_,_=motor
    r=service.responder('Soy adulto y quiero renovar mi DNI y rectificar mis nombres. ¿Cuánto cuesta?')
    assert not r['fuentes'] and '60 días' in r['respuesta']
    assert 'no son acumulables' not in r['respuesta']


@pytest.mark.parametrize('variant',['ausente','incompleta','obsoleta','contradictoria'])
def test_integridad_politica_obligatoria(variant,motor):
    from copy import deepcopy
    service,retrieve,_=motor
    docs=deepcopy(retrieve.return_value)
    policy=next(d for d in docs if d['contenido'].startswith('[[REGLA:no_acumulacion]]'))
    if variant=='ausente': docs.remove(policy)
    elif variant=='incompleta': policy['contenido']=policy['contenido'].replace('[[FIN]]','')
    elif variant=='obsoleta': policy['contenido']=policy['contenido'].replace('no son acumulables','son acumulables')
    else: docs.append({**policy,'contenido':policy['contenido'].replace('no son acumulables','son acumulables')})
    retrieve.return_value=docs
    r=service.responder(BASE+' ¿Cuánto cuesta?')
    assert not r['fuentes'] and r['verificacion'].startswith('abstencion_documental')
    assert 'no son acumulables' not in r['respuesta']


@pytest.mark.parametrize('bad',[
    'Las tasas son acumulables y el total es 14 euros.',
    'La tasa única confirmada del caso conjunto es 7 euros.',
    'La rectificación está exonerada.',
])
def test_verificador_no_inventa_importe_conjunto(bad,motor):
    from app.graph.dni_graph import verificar_respuesta
    service,_,_=motor
    r=service.responder(BASE+' ¿Cuánto cuesta?')
    verified=verificar_respuesta({**snapshot(service,r['session_id']),'respuesta_borrador':bad})
    assert verified['respuesta_final']==r['respuesta']
    assert verified['verificacion'].startswith('observada:')
    assert bad not in verified['historial'][-1]['respuesta']


@pytest.mark.parametrize('q',[
    'Soy adulto y quiero renovar mi DNI y cambiar mi estado civil.',
    'Quiero renovar el DNI de mi hijo menor.',
    'Quiero cambiar mi DNI amarillo a azul.',
])
def test_no_extender_a_otros_supuesto(q,motor):
    service,_,_=motor
    r=service.responder(q)
    assert all(f.get('regla')!='no_acumulacion' for f in r['fuentes'])
    assert 'no son acumulables' not in r['respuesta']


def test_respaldo_exacto_de_la_regla_tarifaria(motor,monkeypatch,tmp_path):
    from app.graph import dni_graph
    from app.rag.exact_rules import recuperar_reglas_exactas
    from langchain_core.documents import Document
    from langchain_community.vectorstores import FAISS
    from tests.test_exact_rule_retrieval import LocalVectors
    service,retrieve,_=motor
    indexed=[Document(page_content=d['contenido'],metadata=d['metadata']) for d in retrieve.return_value]
    path=tmp_path/'policy-index';FAISS.from_documents(indexed,LocalVectors()).save_local(str(path))
    retrieve.return_value=[d for d in retrieve.return_value if not d['contenido'].startswith('[[REGLA:no_acumulacion]]')]
    monkeypatch.setattr(dni_graph,'recuperar_reglas_exactas',lambda c,keys:recuperar_reglas_exactas(c,keys,path))
    r=service.responder(BASE+' ¿Cuánto cuesta?')
    policy=next(f for f in r['fuentes'] if f.get('regla')=='no_acumulacion')
    assert policy['recuperacion']=='exacta' and policy['distancia'] is None
    assert 'no son acumulables' in r['respuesta']


def test_repregunta_plural_de_tasas_es_coste(motor):
    service,_,_=motor
    first=service.responder(BASE+' ¿Cuánto cuesta?')
    r=service.responder('¿Y las tasas?',first['session_id'],first['session_token'])
    assert snapshot(service,r['session_id'])['tipo_consulta']=='coste'
    assert '€7' in r['respuesta'] and 'no son acumulables' in r['respuesta']


def test_indice_anterior_sin_politica_no_suple_desde_txt(motor,monkeypatch,tmp_path):
    from app.graph import dni_graph
    from app.rag.exact_rules import recuperar_reglas_exactas
    from langchain_core.documents import Document
    from langchain_community.vectorstores import FAISS
    from tests.test_exact_rule_retrieval import LocalVectors
    service,retrieve,_=motor
    old=[d for d in retrieve.return_value if not d['contenido'].startswith('[[REGLA:no_acumulacion]]')]
    path=tmp_path/'old-index'
    FAISS.from_documents([Document(page_content=d['contenido'],metadata=d['metadata']) for d in old],LocalVectors()).save_local(str(path))
    retrieve.return_value=old
    monkeypatch.setattr(dni_graph,'recuperar_reglas_exactas',lambda c,keys:recuperar_reglas_exactas(c,keys,path))
    r=service.responder(BASE+' ¿Cuánto cuesta?')
    assert not r['fuentes'] and r['verificacion'].startswith('abstencion_documental')
    assert 'no_acumulacion' in r['verificacion']
