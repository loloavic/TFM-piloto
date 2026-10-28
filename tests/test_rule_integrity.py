"""Integridad de resultados semánticos, sin OpenAI ni índice de aplicación."""
from copy import deepcopy
import pytest
from app.graph import dni_graph
from app.graph.classification import clasificar
from tests.test_adult_dni import motor

QUERY = 'Soy adulto y quiero renovar mi DNI. ¿Cuánto demora?'


def target(docs):
    return deepcopy(next(d for d in docs if d['metadata']['archivo'] == 'dni_mayor_renovacion.txt'
                         and d['contenido'].startswith('[[REGLA:plazo]]')))


@pytest.mark.parametrize('variant', ['obsoleta','vacia','incompleta','chunk','regla_metadata'])
def test_semantica_invalida_abstiene(variant,motor):
    service,retrieve,_=motor
    doc=target(retrieve.return_value)
    if variant=='obsoleta': doc['contenido']='[[REGLA:plazo]]El plazo es de 99 meses.[[FIN]]'
    if variant=='vacia': doc['contenido']='[[REGLA:plazo]][[FIN]]'
    if variant=='incompleta': doc['contenido']='[[REGLA:plazo]]Falta el cierre'
    if variant=='chunk': doc['metadata']['chunk']=999
    if variant=='regla_metadata': doc['metadata']['regla']='seguimiento'
    retrieve.return_value=[doc]
    r=service.responder(QUERY)
    assert not r['fuentes']
    assert r['verificacion'].startswith('abstencion_documental')
    assert '99 meses' not in r['respuesta']


@pytest.mark.parametrize('reverse',[False,True])
def test_contradiccion_no_depende_del_orden(reverse,motor):
    service,retrieve,_=motor
    current=target(retrieve.return_value)
    stale={**current,'contenido':'[[REGLA:plazo]]El plazo es de 99 meses.[[FIN]]'}
    retrieve.return_value=[current,stale][::(-1 if reverse else 1)]
    r=service.responder(QUERY)
    assert not r['fuentes'] and r['verificacion'].startswith('abstencion_documental')


def test_duplicados_identicos_validos(motor):
    service,retrieve,_=motor
    current=target(retrieve.return_value)
    retrieve.return_value=[current,deepcopy(current)]
    r=service.responder(QUERY)
    assert len(r['fuentes'])==1 and r['verificacion']=='ok'

@pytest.mark.parametrize('reverse',[False,True])
def test_docstore_contradictorio_abstiene(reverse,motor,monkeypatch,tmp_path):
    from langchain_core.documents import Document
    from langchain_community.vectorstores import FAISS
    from tests.test_exact_rule_retrieval import LocalVectors
    from app.rag.exact_rules import recuperar_reglas_exactas
    service,retrieve,_=motor
    current=target(retrieve.return_value)
    stale={**current,'contenido':'[[REGLA:plazo]]El plazo es de 99 meses.[[FIN]]'}
    docs=[Document(page_content=d['contenido'],metadata=d['metadata'])
          for d in [current,stale][::(-1 if reverse else 1)]]
    path=tmp_path/'conflicting';FAISS.from_documents(docs,LocalVectors()).save_local(str(path))
    retrieve.return_value=[]
    monkeypatch.setattr(dni_graph,'recuperar_reglas_exactas',lambda c,keys:recuperar_reglas_exactas(c,keys,path))
    r=service.responder(QUERY)
    assert not r['fuentes'] and r['verificacion'].startswith('abstencion_documental')
    assert 'versiones_contradictorias' in r['verificacion']


def test_invalida_no_se_rehabilita_por_exacta(motor,monkeypatch):
    from unittest.mock import Mock
    service,retrieve,_=motor
    current=target(retrieve.return_value)
    retrieve.return_value=[{**current,'contenido':'[[REGLA:plazo]]99 meses[[FIN]]'}]
    exact=Mock(return_value=[current]);monkeypatch.setattr(dni_graph,'recuperar_reglas_exactas',exact)
    r=service.responder(QUERY)
    assert not exact.called and not r['fuentes']
    assert 'distinta_del_corpus_vigente' in r['verificacion']


@pytest.mark.parametrize('file',['dni_menor_renovacion.txt','otro.txt'])
def test_archivo_no_autorizado_no_responde(file,motor):
    service,retrieve,_=motor
    current=target(retrieve.return_value)
    current['metadata']['archivo']=file
    retrieve.return_value=[current]
    r=service.responder(QUERY)
    assert not r['fuentes'] and r['verificacion'].startswith('abstencion_documental')


def test_contradiccion_entre_reintentos_no_desaparece(motor):
    from app.graph.adult_context import plan
    service,retrieve,_=motor
    docs=retrieve.return_value
    query='Soy adulto y quiero rectificar mis nombres en mi DNI vencido. ¿Qué documentos debo presentar?'
    s=dni_graph.enriquecer_busqueda(clasificar({'pregunta':query}))
    required=plan(s['contexto_canonico'])
    selected=[deepcopy(d) for d in docs if d['metadata']['archivo'] in required
              and any(d['contenido'].startswith('[[REGLA:'+rule+']]') for rule in required[d['metadata']['archivo']])]
    initial=selected[:1]
    stale={**initial[0],'contenido':initial[0]['contenido'].replace('€7','€99')}
    assert stale['contenido'] != initial[0]['contenido']
    retrieve.side_effect=[initial,selected+[stale]]
    r=dni_graph.recuperar_documentos(s)
    assert not r['fuentes'] and r['estado_documental']=='sin_evidencia'
    assert any('versiones_contradictorias' in x for x in r['rechazos_documentales'])
