import json

from pydantic import SecretStr
import pytest

from app.core.config import settings
from app.services.interpretation_service import InterpretationService
from scripts import evaluate_v2_interpretation as evaluation
from scripts.v2_interpretation_scenarios import ESCENARIOS, packet, request


def run_fake(fake):
    return evaluation.evaluar(InterpretationService(client=fake), modalidad='simulada', simulado=fake)


def test_matriz_completa_es_fixture_no_calidad_llm():
    report = run_fake(evaluation.ProveedorSimulado())
    assert report['modalidad'] == 'simulada' and report['modelo'] == 'fixture_sin_llm'
    assert report['conversaciones'] == 14 and report['turnos'] == 29
    assert report['turnos_no_ejecutados'] == 0 and not report['interrumpida']
    s = report['resumen']
    assert s['clasificacion_correcta'] == s['ruta_correcta'] == s['contrato_valido'] == 29
    assert s['ruta_incorrectamente_autorizada'] == 0
    assert s['aclaracion_necesaria'] == s['aclaracion_necesaria_atendida'] == 8
    assert s['aclaracion_innecesaria'] == s['aclaracion_necesaria_omitida'] == 0
    assert s['abstencion'] == s['abstencion_correcta'] == 4
    assert s['tokens_entrada'] > 0 and s['tokens_salida'] > 0
    assert s['latencia_p95_ms'] >= s['latencia_p50_ms'] >= 0
    assert all(r['fuente_tokens'] == 'estimacion_bytes' for r in report['resultados'])
    assert len(report['huella_prompt']) == len(report['huella_esquema']) == 64


def test_matriz_cubre_categorias_obligatorias():
    assert {e.categoria for e in ESCENARIOS} >= {
        'renovacion_coste', 'primera_inscripcion_cita', 'seguimiento', 'cambio_titular',
        'negacion_rehabilitacion', 'correccion', 'contradiccion_edad',
        'contradiccion_dni_previo', 'documento_acompanante', 'referencias_ambiguas',
        'adulto_sin_corpus', 'duplicado_sin_corpus', 'fuera_alcance', 'edad_no_concluyente'}


def test_json_valido_no_equivale_a_comprension_y_detecta_ruta_insegura():
    class Wrong(evaluation.ProveedorSimulado):
        def create(self, **kwargs):
            self.salida = packet(*request())  # Siempre renovación, ignorando mensaje.
            return super().create(**kwargs)
    report = run_fake(Wrong())
    assert report['resumen']['contrato_valido'] == 29
    assert report['resumen']['clasificacion_correcta'] < 29
    assert report['resumen']['ruta_incorrectamente_autorizada'] > 0
    assert report['resumen']['aclaracion_necesaria_omitida'] > 0


def test_aclaraciones_innecesarias_y_errores_se_miden():
    class Empty(evaluation.ProveedorSimulado):
        def create(self, **kwargs):
            self.salida = packet()
            return super().create(**kwargs)
    report = run_fake(Empty())
    assert report['resumen']['clasificacion_correcta'] == 0
    assert report['resumen']['aclaracion_innecesaria'] > 0
    assert report['resumen']['ruta_incorrectamente_autorizada'] == 0
    assert report['resumen']['aclaracion_necesaria_atendida'] == 8


def test_timeout_detiene_batch_y_distingue_casos_no_ejecutados():
    class Timeout(evaluation.ProveedorSimulado):
        def create(self, **kwargs):
            raise TimeoutError('NO_LOG_PAYLOAD')
    report = run_fake(Timeout())
    assert report['interrumpida'] and report['turnos'] == 1
    assert report['turnos_no_ejecutados'] == 28
    assert report['resumen']['clasificacion_correcta'] == 0
    assert 'NO_LOG_PAYLOAD' not in json.dumps(report)


def test_informe_solo_categorias_y_metricas():
    report = run_fake(evaluation.ProveedorSimulado())
    encoded = json.dumps(report, ensure_ascii=False)
    for scenario in ESCENARIOS:
        for turn in scenario.turnos:
            assert turn.mensaje not in encoded
    assert not {'mensaje', 'salida', 'evidencias', 'credenciales'} & report['resultados'][0].keys()
    assert {row['decision_obtenida'] for row in report['resultados']} <= {
        'documentada', 'aclaracion', 'abstencion'}


def test_modalidades_no_se_mezclan():
    with pytest.raises(ValueError, match='modalidad_invalida'):
        evaluation.evaluar(None, modalidad='otro')
    with pytest.raises(ValueError, match='proveedor_modalidad_incompatible'):
        evaluation.evaluar(None, modalidad='real', simulado=evaluation.ProveedorSimulado())
    with pytest.raises(ValueError, match='proveedor_modalidad_incompatible'):
        evaluation.evaluar(None, modalidad='simulada')


def test_cli_por_defecto_no_crea_openai_y_guarda_json(tmp_path, monkeypatch, capsys):
    import app.services.interpretation_service as module
    def forbidden(**kwargs):
        pytest.fail('El modo por defecto no debe crear OpenAI')
    monkeypatch.setattr(module, 'OpenAI', forbidden)
    path = tmp_path / 'resultados.json'
    assert evaluation.main(['--output', str(path)]) == 0
    stdout = json.loads(capsys.readouterr().out)
    assert json.loads(path.read_text()) == stdout
    assert stdout['modalidad'] == 'simulada'


@pytest.mark.parametrize('key', [None, SecretStr(''), SecretStr('  ')])
def test_cli_real_requiere_configuracion_antes_de_crear_servicio(monkeypatch, capsys, key):
    monkeypatch.setattr(settings, 'openai_api_key', key)
    def forbidden(**kwargs):
        pytest.fail('No debe construir servicio sin configuración')
    monkeypatch.setattr(evaluation, 'InterpretationService', forbidden)
    assert evaluation.main(['--real']) == 2
    captured = capsys.readouterr()
    assert captured.out == '' and 'no ejecutada' in captured.err


def test_cli_devuelve_fallo_ante_json_valido_semanticamente_incorrecto(monkeypatch, capsys):
    class Wrong(evaluation.ProveedorSimulado):
        def create(self, **kwargs):
            self.salida = packet(*request())
            return super().create(**kwargs)
    monkeypatch.setattr(evaluation, 'ProveedorSimulado', Wrong)
    assert evaluation.main(['--simulated']) == 1
    assert json.loads(capsys.readouterr().out)['resumen']['ruta_incorrectamente_autorizada'] > 0
