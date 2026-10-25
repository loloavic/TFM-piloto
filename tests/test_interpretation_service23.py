from copy import deepcopy
import json
from types import SimpleNamespace as NS

import httpx
from jsonschema import Draft202012Validator
from openai import OpenAI,APIConnectionError,APITimeoutError
from pydantic import SecretStr
import pytest

from app.core.config import settings
from app.graph.canonical_adapter import adaptar_contrato
from app.graph.context_policy import validar_contexto
from app.graph.interpretation_candidate import InterpretacionCandidata
from app.services.interpretation_service import InterpretationService
from app.services.interpretation_service23 import InterpretationService23,esquema_estricto23,VERSION
from scripts.v23_interpretation_scenarios import clear,p,fact,operation,support,objective
from scripts.v2_interpretation_scenarios import packet,request


def response(payload=...,**kwargs):
    return NS(status=kwargs.get('status','completed'),output=kwargs.get('output',[]),
              usage=kwargs.get('usage'),output_text=json.dumps(clear() if payload is ... else payload))


class Fake:
    def __init__(self,*results):self.results=list(results);self.responses=self;self.calls=[];self.closed=False
    def create(self,**kwargs):
        self.calls.append(kwargs)
        item=self.results.pop(0)
        if isinstance(item,Exception):raise item
        return item
    def close(self):self.closed=True


def context23():return adaptar_contrato(None,dict(turno=1,revision=0),clear(),version=VERSION).contexto_canonico


def test_esquema_remoto_estricto_sin_listas_redundantes():
    schema=esquema_estricto23()
    Draft202012Validator.check_schema(schema)
    assert schema['properties']['version']['enum']==[VERSION]
    def check(node):
        if isinstance(node,dict):
            assert 'default' not in node and node.get('type')!='array'
            if node.get('type')=='object':
                assert node['additionalProperties'] is False
                assert set(node['required'])==set(node['properties'])
            for value in node.values():check(value)
        elif isinstance(node,list):
            for value in node:check(value)
    check(schema)
    Draft202012Validator(schema).validate(InterpretacionCandidata.model_validate(clear()).model_dump())
    assert not {'faltantes','evidencias','contradicciones','no_mencionadas'} & schema['properties'].keys()


def test_productor_conecta_adaptador_y_politica_real_multivuelta():
    fake=Fake(response(),response(p(objetivo=objective('referencia_contextual','actual'),
                                    tema=fact('coste','solicitud_afirmativa'))))
    service=InterpretationService23(client=fake)
    r=service.interpretar('Solicitud sintética')
    assert r.estado=='ok' and r.transicion.ruta=='dni_menor_renovacion'
    c=deepcopy(r.contexto_canonico)
    n=service.interpretar('Repregunta sintética',c,diagnostico=True)
    assert n.transicion.ruta=='dni_menor_renovacion'
    for key in ('objetivo','edad','operacion'):assert n.contexto_canonico[key]==c[key]
    assert c==r.contexto_canonico
    call=fake.calls[0]
    assert call['model']==settings.openai_model and call['store'] is False
    assert call['text']['format']['strict'] is True
    assert call['timeout']==settings.provider_timeout_seconds and call['max_output_tokens']==1600
    assert not {'tools','conversation','previous_response_id','metadata'} & call.keys()
    service.close();assert fake.closed


def test_minimizacion_y_contexto_solo_neutral():
    c=context23();c['ultima_ruta']='PRIVATE_HISTORY'
    fake=Fake(response())
    result=InterpretationService23(client=fake).interpretar('DNI: 12345678 correo prueba@example.test',c)
    sent=json.loads(fake.calls[0]['input'][0]['content'])
    assert '12345678' not in sent['mensaje'] and 'prueba@example.test' not in sent['mensaje']
    assert 'objetivo' in sent['contexto'] and 'titular' not in sent['contexto']
    assert not {'historial','ultima_ruta','turno','revision'} & sent['contexto'].keys()
    assert 'PRIVATE_HISTORY' not in json.dumps(sent)
    assert 'prueba@example.test' not in repr(result)


def test_version23_rechaza_sesion22_antes_de_llamar_proveedor():
    c=adaptar_contrato(None,dict(turno=1,revision=0),packet(*request()),version='2.2').contexto_canonico
    fake=Fake()
    result=InterpretationService23(client=fake).interpretar('Consulta',c)
    assert result.estado=='version_estado_incompatible' and not fake.calls
    assert not result.transicion.ruta and 'objetivo' not in result.contexto_canonico


def test_version22_rechaza_sesion_neutral_antes_de_llamar_proveedor():
    fake=Fake()
    result=InterpretationService(client=fake).interpretar('Consulta',context23())
    assert result.estado=='version_estado_incompatible' and not fake.calls
    assert result.contexto_canonico['pendientes']


@pytest.mark.parametrize('message',[None,42,True,'','  ','x'*8001,{}])
def test_entrada_invalida_sin_red(message):
    fake=Fake()
    result=InterpretationService23(client=fake).interpretar(message)
    assert result.estado=='entrada_invalida' and not fake.calls and not result.transicion.ruta
    assert 'objetivo' in result.contexto_canonico and validar_contexto(result.contexto_canonico)


def test_contexto_corrupto_no_sale_ni_se_registra(caplog):
    c=context23();c['nombre']='SENSITIVE_SENTINEL'
    fake=Fake()
    result=InterpretationService23(client=fake).interpretar('Consulta',c,diagnostico=True)
    assert not fake.calls and not result.transicion.ruta
    assert 'SENSITIVE_SENTINEL' not in repr(result)+caplog.text


@pytest.mark.parametrize('payload',[None,{},[],dict(clear(),ruta='dni_menor_renovacion'),
                                    dict(clear(),nombre='SENSITIVE_SENTINEL')])
def test_respuesta_invalida_sin_fallback(payload,caplog):
    result=InterpretationService23(client=Fake(response(payload))).interpretar('Consulta',context23(),diagnostico=True)
    assert result.estado=='respuesta_invalida' and result.interpretacion is None
    assert not result.transicion.ruta and 'SENSITIVE_SENTINEL' not in repr(result)+caplog.text


@pytest.mark.parametrize('text,code',[
    ('not-json','json_invalido'),('x'*16385,'limite_excedido'),
    ('{"version":"2.3-candidata-1","edad":{},"edad":{}}','clave_duplicada'),
    ('{"version":"2.3-candidata-1","operaciones":{"renovacion":{"negacion":null,"negacion":null}}}','clave_duplicada'),
])
def test_json_no_se_repara(text,code):
    r=response();r.output_text=text
    result=InterpretationService23(client=Fake(r)).interpretar('Consulta',context23())
    assert result.codigo_validacion==code and not result.transicion.ruta


@pytest.mark.parametrize('status',['incomplete','failed','cancelled','in_progress'])
def test_no_acepta_json_parcial(status):
    result=InterpretationService23(client=Fake(response(status=status))).interpretar('Consulta',context23())
    assert result.estado=='respuesta_incompleta' and result.interpretacion is None
    assert not result.transicion.ruta


def test_refusal_no_se_usa_ni_se_loguea(caplog):
    r=response(output=[NS(content=[NS(type='refusal',refusal='SENSITIVE_SENTINEL')])])
    result=InterpretationService23(client=Fake(r)).interpretar('Consulta',context23())
    assert result.estado=='rechazo_proveedor' and not result.transicion.ruta
    assert 'SENSITIVE_SENTINEL' not in repr(result)+caplog.text


@pytest.mark.parametrize('error,state',[
    (TimeoutError('SENSITIVE_SENTINEL'),'timeout'),
    (APITimeoutError(request=httpx.Request('POST','https://api.openai.com/v1/responses')),'timeout'),
    (APIConnectionError(request=httpx.Request('POST','https://api.openai.com/v1/responses')),'error_proveedor'),
    (RuntimeError('SENSITIVE_SENTINEL'),'error_interprete'),
])
def test_errores_seguro_sin_excepciones_en_logs(error,state,caplog,capsys):
    result=InterpretationService23(client=Fake(error)).interpretar('SENSITIVE_SENTINEL',context23())
    assert result.estado==state and not result.transicion.ruta
    captured=capsys.readouterr()
    assert 'SENSITIVE_SENTINEL' not in repr(result)+caplog.text+captured.out+captured.err


def test_error_inicial_no_cambia_version_de_sesion_y_recupera_con_solicitud_completa():
    service=InterpretationService23(client=Fake(TimeoutError(),response()))
    first=service.interpretar('Consulta')
    assert first.contexto_canonico['objetivo']['estado']=='desconocido'
    assert first.transicion.traza['campos']['objetivo']['despues']==first.contexto_canonico['objetivo']
    second=service.interpretar('Solicitud nueva completa',first.contexto_canonico)
    assert second.transicion.ruta=='dni_menor_renovacion'


def test_fuera_alcance_conserva_formato23_sin_heredar_identidad():
    service=InterpretationService23(client=Fake(response(p(ambito=fact('fuera_alcance'))),response()))
    first=service.interpretar('Consulta fuera de alcance',context23())
    assert first.estado=='ok' and first.contexto_canonico['objetivo']['estado']=='desconocido'
    assert not first.transicion.ruta
    assert service.interpretar('Consulta nueva',first.contexto_canonico).transicion.ruta=='dni_menor_renovacion'


def test_solicitud_y_negacion_se_preservan_y_bloquean():
    result=InterpretationService23(client=Fake(response(p(operaciones={'renovacion':{
        'solicitud':support(),'negacion':support()}})))).interpretar('Consulta',context23())
    assert result.estado=='ok' and result.estado_interpretacion=='contradictorio'
    assert result.interpretacion.operaciones.renovacion.solicitud
    assert result.interpretacion.operaciones.renovacion.negacion
    assert not result.transicion.ruta


@pytest.mark.parametrize('usage,source',[(None,'estimacion_bytes'),
    (NS(input_tokens=100,output_tokens=50),'proveedor'),(NS(input_tokens=True,output_tokens=-1),'estimacion_bytes')])
def test_metricas(usage,source):
    r=InterpretationService23(client=Fake(response(usage=usage))).interpretar('Consulta')
    assert r.metricas.fuente_tokens==source and r.metricas.latencia_ms>=0
    assert r.metricas.tokens_entrada>0 and r.metricas.tokens_salida>0


def test_logging_debug_bloquea_sin_cambiar_logger(caplog):
    import logging
    fake=Fake(response())
    with caplog.at_level(logging.DEBUG,logger='openai._base_client'):
        result=InterpretationService23(client=fake).interpretar('SENSITIVE_SENTINEL')
    assert result.estado=='registro_inseguro' and not fake.calls
    assert 'SENSITIVE_SENTINEL' not in caplog.text


def test_reutiliza_configuracion_y_no_reintenta(monkeypatch):
    import app.services.interpretation_service23 as module
    fake=Fake(response());captured={}
    def factory(**kwargs):captured.update(kwargs);return fake
    monkeypatch.setattr(settings,'openai_api_key',SecretStr('test-only'))
    monkeypatch.setattr(module,'OpenAI',factory)
    result=InterpretationService23().interpretar('Consulta')
    assert result.estado=='ok'
    assert captured==dict(api_key='test-only',timeout=settings.provider_timeout_seconds,max_retries=0)


@pytest.mark.parametrize('key',[None,SecretStr(''),SecretStr(' ')])
def test_configuracion_ausente_no_crea_cliente(monkeypatch,key):
    import app.services.interpretation_service23 as module
    monkeypatch.setattr(settings,'openai_api_key',key)
    def forbidden(**kwargs):pytest.fail('No debe crear cliente')
    monkeypatch.setattr(module,'OpenAI',forbidden)
    result=InterpretationService23().interpretar('Consulta')
    assert result.estado=='sin_configuracion' and not result.transicion.ruta


def test_sdk_real_transporte_simulado_serializa_esquema_y_uso():
    requests=[]
    def handle(req):
        body=json.loads(req.content);requests.append(body)
        payload=InterpretacionCandidata.model_validate(clear()).model_dump()
        Draft202012Validator(body['text']['format']['schema']).validate(payload)
        return httpx.Response(200,json={'id':'resp_test','object':'response','created_at':0,
            'status':'completed','model':settings.openai_model,'output':[{'id':'msg_test','type':'message',
            'role':'assistant','status':'completed','content':[{'type':'output_text',
            'text':json.dumps(payload),'annotations':[]}]}],
            'usage':{'input_tokens':100,'output_tokens':50,'total_tokens':150}})
    client=OpenAI(api_key='test-only',max_retries=0,http_client=httpx.Client(transport=httpx.MockTransport(handle)))
    service=InterpretationService23(client=client)
    result=service.interpretar('Consulta sintética');service.close()
    assert result.estado=='ok' and result.transicion.ruta=='dni_menor_renovacion'
    assert len(requests)==1 and requests[0]['store'] is False
    assert result.metricas.tokens_entrada==100 and result.metricas.tokens_salida==50


def test_sdk_timeout_sin_reintentos():
    calls=[]
    def handle(req):calls.append(req);raise httpx.ReadTimeout('SENSITIVE_SENTINEL',request=req)
    client=OpenAI(api_key='test-only',max_retries=0,http_client=httpx.Client(transport=httpx.MockTransport(handle)))
    service=InterpretationService23(client=client)
    result=service.interpretar('Consulta');service.close()
    assert result.estado=='timeout' and len(calls)==1 and not result.transicion.ruta
