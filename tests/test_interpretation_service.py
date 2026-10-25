from copy import deepcopy
import json
from types import SimpleNamespace as NS

import httpx
from openai import APIConnectionError, APITimeoutError, BadRequestError, OpenAI
from pydantic import SecretStr
import pytest

from app.core.config import settings
from app.graph.context_policy import ruta_documental
from app.graph.interpretation_contract import InterpretacionTurno
from app.graph.interpretation_adapter import adaptar_interpretacion
from app.services.interpretation_service import (
    InterpretationService, esquema_estricto, resumen_canonico,
)
from scripts.v2_interpretation_scenarios import atom, packet, request


def response(payload=None, *, status='completed', output=None, usage=None):
    return NS(status=status, output=output or [], usage=usage,
              output_text=json.dumps(packet(*request()) if payload is None else payload))


class Fake:
    def __init__(self, *results):
        self.results = list(results)
        self.calls = []
        self.responses = self
        self.closed = False

    def create(self, **kwargs):
        self.calls.append(kwargs)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def close(self):
        self.closed = True


def base():
    return adaptar_interpretacion(None, dict(turno=1, revision=0), packet(*request()))


def test_servicio_conecta_con_adaptador_y_no_autoriza_por_json():
    fake = Fake(response(), response(packet(atom('tema', 'coste', 'solicitud_afirmativa'))))
    service = InterpretationService(client=fake)
    first = service.interpretar('Quiero renovar el DNI de mi hijo menor.')
    assert first.estado == 'ok' and ruta_documental(first.contexto_canonico) == 'dni_menor_renovacion'
    second = service.interpretar('¿Cuánto cuesta?', first.contexto_canonico)
    assert second.estado_interpretacion == 'requiere_aclaracion'  # Local al turno.
    assert ruta_documental(second.contexto_canonico) == 'dni_menor_renovacion'
    assert second.contexto_canonico['operacion'] == first.contexto_canonico['operacion']
    call = fake.calls[0]
    assert call['model'] == settings.openai_model
    assert call['store'] is False and call['text']['format']['strict'] is True
    assert call['text']['format']['type'] == 'json_schema'
    assert call['timeout'] == settings.provider_timeout_seconds
    assert call['max_output_tokens'] == 1600
    assert not {'previous_response_id', 'conversation', 'tools', 'metadata'} & call.keys()
    service.close()
    assert fake.closed


def test_esquema_cerrado_y_requerido():
    schema = esquema_estricto()
    assert schema['properties']['version']['enum'] == ['2.1', '2.2']
    def check(node):
        if isinstance(node,dict):
            if node.get('type')=='object':
                assert node['additionalProperties'] is False
                assert set(node['required'])==set(node['properties'])
            for value in node.values():check(value)
        elif isinstance(node,list):
            for value in node:check(value)
    check(schema)
    assert not {'ruta', 'confianza', 'identidad'} & schema['properties'].keys()


def test_minimizacion_y_resumen_sin_historial_o_rutas():
    c = base()
    c['ultima_ruta'] = 'dni_menor_renovacion'
    before = deepcopy(c)
    fake = Fake(response())
    result = InterpretationService(client=fake).interpretar(
        'Mi DNI: 12345678 y correo prueba@example.test. ¿Cuánto cuesta?', c)
    sent = json.loads(fake.calls[0]['input'][0]['content'])
    assert '12345678' not in sent['mensaje'] and 'prueba@example.test' not in sent['mensaje']
    assert 'REDACTADO' in sent['mensaje']
    assert set(sent) == {'mensaje', 'contexto'}
    assert not {'historial', 'ultima_ruta', 'propuesta_operacion', 'turno', 'revision'} & sent['contexto'].keys()
    assert set(sent['contexto']['edad']) == {'valor', 'estado', 'origen'}
    assert c == before
    assert 'prueba@example.test' not in repr(result)


@pytest.mark.parametrize('message', [None, 123, True, '', '  ', 'x' * 8001, {}])
def test_entrada_invalida_no_llama_proveedor(message):
    fake = Fake()
    result = InterpretationService(client=fake).interpretar(message, base())
    assert not fake.calls and result.estado == 'entrada_invalida'
    assert not ruta_documental(result.contexto_canonico)


def test_contexto_extra_no_se_envia_ni_persiste():
    c = base()
    c['historial'] = [{'content': 'SENSITIVE_SENTINEL'}]
    fake = Fake()
    result = InterpretationService(client=fake).interpretar('¿Y el coste?', c)
    assert not fake.calls and not ruta_documental(result.contexto_canonico)
    assert 'SENSITIVE_SENTINEL' not in repr(result)
    with pytest.raises(ValueError, match='contexto_invalido'):
        resumen_canonico(c)


@pytest.mark.parametrize('payload', [None, {}, [], {'version': '2.1'},
    dict(version='2.1', evidencias=[], faltantes=[], contradicciones=[]),
    dict(version='2.1', evidencias=[], faltantes=[], contradicciones=[], ruta='dni_menor_renovacion')])
def test_salida_invalida_bloquea_sin_fallback(payload):
    r = response()
    r.output_text = json.dumps(payload)
    result = InterpretationService(client=Fake(r)).interpretar('¿Cuánto cuesta?', base())
    assert result.estado == 'respuesta_invalida'
    assert result.interpretacion is None and not ruta_documental(result.contexto_canonico)


@pytest.mark.parametrize('text', ['not-json', '```json\n{}\n```',
    '{"version":"2.1","version":"2.1"}', 'x' * 16385])
def test_json_invalido_no_se_repara(text):
    r = response()
    r.output_text = text
    result = InterpretationService(client=Fake(r)).interpretar('Consulta sintética', base())
    assert result.estado == 'respuesta_invalida' and not ruta_documental(result.contexto_canonico)


@pytest.mark.parametrize('status', ['incomplete', 'failed', 'cancelled', 'in_progress'])
def test_no_acepta_json_parcial_de_respuesta_no_completada(status):
    result = InterpretationService(client=Fake(response(status=status))).interpretar('Consulta', base())
    assert result.estado == 'respuesta_incompleta'
    assert not ruta_documental(result.contexto_canonico)


def test_rechazo_del_modelo_no_se_confunde_con_json_valido():
    refusal = [NS(content=[NS(type='refusal', refusal='SENSITIVE_SENTINEL')])]
    result = InterpretationService(client=Fake(response(output=refusal))).interpretar('Consulta', base())
    assert result.estado == 'rechazo_proveedor'
    assert not ruta_documental(result.contexto_canonico)
    assert 'SENSITIVE_SENTINEL' not in repr(result)


@pytest.mark.parametrize('error,code', [
    (TimeoutError('SENSITIVE_SENTINEL'), 'timeout'),
    (APITimeoutError(request=httpx.Request('POST', 'https://api.openai.com/v1/responses')), 'timeout'),
    (APIConnectionError(request=httpx.Request('POST', 'https://api.openai.com/v1/responses')), 'error_proveedor'),
    (BadRequestError('SENSITIVE_SENTINEL', response=httpx.Response(400,
        request=httpx.Request('POST', 'https://api.openai.com/v1/responses')),
        body={'error': 'SENSITIVE_SENTINEL'}), 'error_proveedor'),
])
def test_errores_sin_logs_ni_payloads(error, code, caplog, capsys):
    result = InterpretationService(client=Fake(error)).interpretar('SENSITIVE_SENTINEL', base())
    assert result.estado == code and not ruta_documental(result.contexto_canonico)
    captured = capsys.readouterr()
    assert 'SENSITIVE_SENTINEL' not in captured.out + captured.err + caplog.text + repr(result)


def test_json_semanticamente_contradictorio_no_autoriza():
    p = packet(*request(), atom('edad', 'adulto'))
    result = InterpretationService(client=Fake(response(p))).interpretar('Consulta sintética', base())
    assert result.estado == 'ok' and result.estado_interpretacion == 'requiere_aclaracion'
    assert not ruta_documental(result.contexto_canonico)


def test_valor_incompatible_con_dimension_no_pasa_validacion_local():
    p = packet(atom('edad', 'renovacion'))
    result = InterpretationService(client=Fake(response(p))).interpretar('Consulta')
    assert result.estado == 'respuesta_invalida'
    assert not ruta_documental(result.contexto_canonico)


@pytest.mark.parametrize('usage,source', [(NS(input_tokens=15, output_tokens=20), 'proveedor'),
    (None, 'estimacion_bytes'), (NS(input_tokens=True, output_tokens=-1), 'estimacion_bytes')])
def test_metricas_sin_texto(usage, source):
    result = InterpretationService(client=Fake(response(usage=usage))).interpretar('Consulta')
    metrics = result.metricas
    assert metrics.fuente_tokens == source and metrics.latencia_ms >= 0
    assert metrics.tokens_entrada > 0 and metrics.tokens_salida > 0
    if source == 'proveedor':
        assert metrics.tokens_entrada == 15 and metrics.tokens_salida == 20


def test_configuracion_existente_reutilizada_sin_alterar_v1(monkeypatch):
    import app.services.interpretation_service as module
    fake = Fake(response())
    captured = {}
    def create(**kwargs):
        captured.update(kwargs)
        return fake
    monkeypatch.setattr(settings, 'openai_api_key', SecretStr('test-only'))
    monkeypatch.setattr(module, 'OpenAI', create)
    r = InterpretationService().interpretar('Consulta')
    assert captured == dict(api_key='test-only', timeout=settings.provider_timeout_seconds, max_retries=0)
    assert r.estado == 'ok'


@pytest.mark.parametrize('key', [None, SecretStr(''), SecretStr('  ')])
def test_sin_configuracion_no_crea_cliente(monkeypatch, key):
    import app.services.interpretation_service as module
    monkeypatch.setattr(settings, 'openai_api_key', key)
    def forbidden(**kwargs):
        pytest.fail('No debe crear cliente sin configuración')
    monkeypatch.setattr(module, 'OpenAI', forbidden)
    result = InterpretationService().interpretar('Consulta', base())
    assert result.estado == 'sin_configuracion' and not ruta_documental(result.contexto_canonico)


def test_sdk_real_con_transporte_http_simulado_sin_red():
    calls = []
    def handle(request_http):
        calls.append(json.loads(request_http.content))
        return httpx.Response(200, json={
            'id': 'resp_synthetic', 'object': 'response', 'created_at': 0,
            'model': settings.openai_model, 'status': 'completed',
            'output': [{'type': 'message', 'id': 'msg_synthetic', 'role': 'assistant',
                        'status': 'completed', 'content': [{'type': 'output_text',
                        'text': json.dumps(InterpretacionTurno.model_validate(packet(*request())).model_dump()), 'annotations': []}]}],
            'usage': {'input_tokens': 100, 'output_tokens': 80, 'total_tokens': 180},
        })
    client = OpenAI(api_key='test-only', max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handle)))
    service = InterpretationService(client=client)
    result = service.interpretar('Consulta sintética')
    service.close()
    assert len(calls) == 1 and calls[0]['text']['format']['strict'] is True
    assert calls[0]['store'] is False
    assert result.estado == 'ok' and result.metricas.fuente_tokens == 'proveedor'
    assert ruta_documental(result.contexto_canonico) == 'dni_menor_renovacion'


def test_timeout_sdk_sin_reintentos():
    calls = []
    def handle(req):
        calls.append(req)
        raise httpx.ReadTimeout('SENSITIVE_SENTINEL', request=req)
    client = OpenAI(api_key='test-only', max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handle)))
    service = InterpretationService(client=client)
    result = service.interpretar('Consulta', base())
    service.close()
    assert result.estado == 'timeout' and len(calls) == 1
    assert not ruta_documental(result.contexto_canonico)


def test_logging_debug_inseguro_bloquea_sin_reconfigurar_logging(caplog):
    import logging
    fake = Fake(response())
    with caplog.at_level(logging.DEBUG, logger='openai._base_client'):
        result = InterpretationService(client=fake).interpretar('SENSITIVE_SENTINEL', base())
        assert logging.getLogger('openai._base_client').isEnabledFor(logging.DEBUG)
    assert result.estado == 'registro_inseguro' and not fake.calls
    assert not ruta_documental(result.contexto_canonico)
    assert 'SENSITIVE_SENTINEL' not in caplog.text


def test_error_inesperado_no_filtra_traceback(caplog, capsys):
    fake = Fake(RuntimeError('SENSITIVE_SENTINEL'))
    result = InterpretationService(client=fake).interpretar('SENSITIVE_SENTINEL', base())
    assert result.estado == 'error_interprete'
    assert not ruta_documental(result.contexto_canonico)
    captured = capsys.readouterr()
    assert 'SENSITIVE_SENTINEL' not in caplog.text + captured.out + captured.err + repr(result)
