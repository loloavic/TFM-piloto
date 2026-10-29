"""Regla indexada pero excluida del ranking; no proveedor externo."""
from unittest.mock import Mock
from tests.test_adult_dni import motor, snapshot
from tests.test_widow_answers import PENDING

FOLLOWUP='Ya han pasado cuatro meses desde mi trámite. ¿Cómo puedo consultar el estado de mi DNI y saber si está disponible para recogerlo?'


def test_regla_fuera_top_k_se_recupera_exactamente(motor,monkeypatch):
    from app.graph import dni_graph
    service,retrieve,prompts=motor
    complete=retrieve.return_value
    omitted=[d for d in complete if not d['contenido'].startswith('[[REGLA:seguimiento]]')]
    target=[d for d in complete if d['metadata']['archivo']=='dni_mayor_estado_civil.txt'
            and d['contenido'].startswith('[[REGLA:seguimiento]]')]
    exact=Mock(return_value=target)
    monkeypatch.setattr(dni_graph,'recuperar_reglas_exactas',exact,raising=False)
    first=service.responder(PENDING+' Mi esposo era italiano')
    retrieve.return_value=omitted
    r=service.responder(FOLLOWUP,first['session_id'],first['session_token'])
    assert exact.call_count == 1
    assert {f['archivo'] for f in r['fuentes']} == {'dni_mayor_estado_civil.txt'}
    assert {f['regla'] for f in r['fuentes']} == {'seguimiento'}
    assert 'no constituye' in r['respuesta'] and not prompts
    assert not snapshot(service,first['session_id'])['reglas_faltantes']


import pytest
from langchain_core.embeddings import Embeddings
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from app.graph.classification import clasificar
from app.rag import exact_rules
from app.rag.document_loader import cargar_documentos_txt
from app.rag.text_splitter import dividir_documentos


class LocalVectors(Embeddings):
    """Vectores artificiales: excluyen seguimiento de cualquier top-10."""
    def embed_documents(self,texts):
        return [[100.0] if '[[REGLA:seguimiento]]' in text else [0.0] for text in texts]
    def embed_query(self,text):
        return [0.0]


@pytest.fixture
def indexed(tmp_path):
    fragments=dividir_documentos(cargar_documentos_txt())
    docs=[Document(page_content=f['contenido'],metadata={k:f[k] for k in ['archivo','chunk','id']}) for f in fragments]
    store=FAISS.from_documents(docs,LocalVectors())
    path=tmp_path/'index'
    store.save_local(str(path))
    return path,store,fragments


def context():
    s=clasificar({'pregunta':PENDING+' Mi esposo era italiano'})
    return clasificar({**s,'pregunta':FOLLOWUP})['contexto_canonico']


def test_faiss_local_regla_real_fuera_del_ranking_y_lectura_sin_embeddings(indexed):
    path,store,fragments=indexed
    ranked=store.similarity_search_with_score(FOLLOWUP,k=10)
    assert len(ranked)==10
    assert all('[[REGLA:seguimiento]]' not in doc.page_content for doc,_ in ranked)
    retry=store.similarity_search_with_score(FOLLOWUP+' Fuente dni_mayor_estado_civil.txt REGLA seguimiento',k=10)
    assert all('[[REGLA:seguimiento]]' not in doc.page_content for doc,_ in retry)
    found=exact_rules.recuperar_reglas_exactas(context(),{('dni_mayor_estado_civil.txt','seguimiento')},path)
    assert len(found)==1 and found[0]['score'] is None
    assert found[0]['metadata']['archivo']=='dni_mayor_estado_civil.txt'
    assert found[0]['metadata']['recuperacion']=='exacta'
    assert 'no constituye' in found[0]['contenido']
    assert len(fragments)==44


@pytest.mark.parametrize('body',[
    '[[REGLA:seguimiento]]Falta cierre',
    'Fragmento antiguo sin marcadores',
    '[[REGLA:seguimiento]][[FIN]]',
    '[[REGLA:plazo]]Otra regla[[FIN]]',
])
def test_indice_antiguo_incompleto_o_regla_incorrecta_abstiene(body,tmp_path):
    doc=Document(page_content=body,metadata={'archivo':'dni_mayor_estado_civil.txt','chunk':0})
    store=FAISS.from_documents([doc],LocalVectors())
    path=tmp_path/'old';store.save_local(str(path))
    assert exact_rules.recuperar_reglas_exactas(context(),{('dni_mayor_estado_civil.txt','seguimiento')},path)==[]


def test_pares_no_autorizados_no_abren_el_indice(monkeypatch):
    load=Mock(side_effect=AssertionError('no debe abrirse'))
    monkeypatch.setattr(exact_rules,'cargar_indice_exacto',load)
    assert exact_rules.recuperar_reglas_exactas(context(),{('dni_menor_renovacion.txt','general')})==[]
    assert exact_rules.recuperar_reglas_exactas(context(),{('dni_mayor_estado_civil.txt','plazo')})==[]
    assert not load.called


def test_regla_ausente_no_se_suple_desde_txt(tmp_path):
    store=FAISS.from_documents([Document(page_content='Texto ajeno',metadata={'archivo':'dni_menor_renovacion.txt','chunk':0})],LocalVectors())
    path=tmp_path/'absent';store.save_local(str(path))
    assert exact_rules.recuperar_reglas_exactas(context(),{('dni_mayor_estado_civil.txt','seguimiento')},path)==[]


@pytest.mark.parametrize('start,file',[
    ('Soy adulto y quiero renovar mi DNI','dni_mayor_renovacion.txt'),
    ('Soy adulto y quiero rectificar nombres en mi DNI','dni_mayor_rectificacion.txt'),
    (PENDING+' Mi esposo era italiano','dni_mayor_estado_civil.txt'),
])
@pytest.mark.parametrize('query,rule',[
    ('¿Cuánto demora?','plazo'),('¿Qué advertencias debo tener en cuenta?','advertencias'),(FOLLOWUP,'seguimiento')])
def test_fallback_exacto_se_limita_a_la_modalidad_y_regla(start,file,query,rule,motor,monkeypatch,indexed):
    from app.graph import dni_graph
    path,_,_=indexed
    service,retrieve,prompts=motor
    first=service.responder(start)
    retrieve.return_value=[]
    monkeypatch.setattr(dni_graph,'recuperar_reglas_exactas',lambda c,keys:exact_rules.recuperar_reglas_exactas(c,keys,path))
    result=service.responder(query,first['session_id'],first['session_token'])
    assert {f['archivo'] for f in result['fuentes']}=={file}
    assert {f['regla'] for f in result['fuentes']}=={rule}
    assert all(f['recuperacion']=='exacta' and f['distancia'] is None for f in result['fuentes'])
    if rule=='seguimiento': assert 'no constituye' in result['respuesta']


def test_api_y_gradio_representan_lectura_exacta_sin_distancia_ficticia(motor,monkeypatch,indexed):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.graph import dni_graph
    from app import ui
    path,_,_=indexed
    service,retrieve,_=motor
    retrieve.return_value=[]
    monkeypatch.setattr(dni_graph,'recuperar_reglas_exactas',lambda c,keys:exact_rules.recuperar_reglas_exactas(c,keys,path))
    monkeypatch.setattr(ui,'rag',service)
    query='Soy adulto y quiero renovar mi DNI. ¿Cómo hago seguimiento?'
    with TestClient(app) as client:
        result=client.post('/api/v1/consultas',json={'pregunta':query})
        assert result.status_code==200
        assert result.json()['fuentes'][0]['distancia'] is None
        assert result.json()['fuentes'][0]['recuperacion']=='exacta'
    result=ui.responder_consulta(query,[],ui.generar_session_id())
    assert 'recuperación exacta' in result[3]


def test_diagnostico_detecta_version_desactualizada_y_exacta_abstiene(indexed,tmp_path):
    from app.rag.inspect_rules import diagnosticar_indice
    _,_,fragments=indexed
    target=next(f for f in fragments if f['archivo']=='dni_mayor_estado_civil.txt' and f['contenido'].startswith('[[REGLA:seguimiento]]'))
    wrong=target['contenido'].replace('100 %','90 %')
    store=FAISS.from_documents([Document(page_content=wrong,metadata={'archivo':target['archivo'],'chunk':target['chunk']})],LocalVectors())
    path=tmp_path/'stale';store.save_local(str(path))
    report=diagnosticar_indice(path)
    assert report['reglas']['dni_mayor_estado_civil.txt#seguimiento']=='distinta_del_txt_actual'
    assert exact_rules.recuperar_reglas_exactas(context(),{('dni_mayor_estado_civil.txt','seguimiento')},path)==[]


def test_inventario_del_indice_completo_corresponde_a_los_43_fragmentos(indexed):
    from app.rag.inspect_rules import diagnosticar_indice
    path,_,_=indexed
    report=diagnosticar_indice(path)
    assert report['fragmentos_indexados']==report['fragmentos_corpus_actual']==44
    assert not report['fragmentos_invalidos']
    assert set(report['reglas'].values())=={'coincide_con_txt_actual'}


def test_exacta_no_abre_indice_con_contexto_invalido(monkeypatch):
    load=Mock(side_effect=AssertionError('no autorizado'))
    monkeypatch.setattr(exact_rules,'cargar_indice_exacto',load)
    c=context();c['edad']['revision']+=1
    assert exact_rules.recuperar_reglas_exactas(c,{('dni_mayor_estado_civil.txt','seguimiento')})==[]
    assert not load.called
