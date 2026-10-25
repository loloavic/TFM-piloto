from copy import deepcopy
import json

from pydantic import SecretStr
import pytest

from scripts import compare_interpretation_versions as ev
from scripts.v2_interpretation_scenarios import ESCENARIOS
from scripts.v23_interpretation_scenarios import clear,p
from app.graph.interpretation_candidate import InterpretacionCandidata
from app.core.config import settings


def run(fake=None,version=ev.VERSION,**kwargs):
    fake=fake or ev.ProveedorComparativo()
    service=ev.crear_servicio(version,client=fake)
    try:return ev.evaluar_comparativo(service,version=version,modalidad='simulada',simulado=fake,**kwargs)
    finally:service.close()


@pytest.mark.parametrize('version',['2.2',ev.VERSION])
@pytest.mark.parametrize('mode',['conversacion','aislados'])
def test_misma_matriz_politica_real_y_etapas_separadas(version,mode):
    r=run(version=version,modo=mode,diagnostico=True)
    assert r['turnos']==r['turnos_programados']==29 and r['satisfactoria']
    assert r['cobertura_documental']==dict(positivas_esperadas=17,positivas_autorizadas=17,
        autorizaciones_incorrectas=0,aclaraciones_necesarias=8,aclaraciones_atendidas=8,aclaraciones_innecesarias=0)
    for metric in r['metricas_etapas'].values():assert metric['tasa']==1
    assert r['tokens_entrada']>0 and r['tokens_salida']>0
    assert r['latencia_p95_ms']>=r['latencia_p50_ms']>=0
    assert r['modelo']=='fixture_sin_llm' and len(r['huella_prompt'])==len(r['huella_esquema'])==64


def test_json_valido_no_equivale_a_calidad_semantica():
    class AlwaysRenewal(ev.ProveedorComparativo):
        def create(self,**kwargs):
            self.salida=InterpretacionCandidata.model_validate(clear()).model_dump()
            return super().create(**kwargs)
    r=run(AlwaysRenewal())
    assert r['metricas_etapas']['contrato']['correctos']==29
    assert r['metricas_etapas']['interpretacion_semantica']['correctos']<29
    assert r['cobertura_documental']['autorizaciones_incorrectas']>0
    assert not r['satisfactoria']


def test_no_se_aprueba_autorizando_cero():
    class Empty(ev.ProveedorComparativo):
        def create(self,**kwargs):
            self.salida=InterpretacionCandidata.model_validate(p()).model_dump()
            return super().create(**kwargs)
    r=run(Empty())
    assert r['metricas_etapas']['contrato']['correctos']==29
    assert r['cobertura_documental']['positivas_autorizadas']==0
    assert r['cobertura_documental']['autorizaciones_incorrectas']==0
    assert not r['satisfactoria']


def test_timeout_no_se_contrapone_como_error_de_esquema():
    class Timeout(ev.ProveedorComparativo):
        def create(self,**kwargs):raise TimeoutError('SENSITIVE_SENTINEL')
    r=run(Timeout())
    assert r['interrumpida'] and r['turnos']==1 and r['turnos_no_ejecutados']==28
    assert r['cobertura_documental']['positivas_esperadas']==17
    assert r['metricas_etapas']['contrato']['evaluables']==0
    assert r['metricas_etapas']['contrato']['tasa'] is None
    assert r['metricas_etapas']['entrega_contrato_valido']['tasa']==0
    assert not r['satisfactoria'] and 'SENSITIVE_SENTINEL' not in json.dumps(r)


def test_arrastre_e_ideal_aislado_no_se_mezclan():
    class FirstBad(ev.ProveedorComparativo):
        def __init__(self):super().__init__();self.n=0
        def create(self,**kwargs):
            self.n+=1
            if self.n==1:self.salida={'version':ev.VERSION,'nombre':'SENSITIVE_SENTINEL'}
            return super().create(**kwargs)
    conv=run(FirstBad(),escenarios=ESCENARIOS[:1],diagnostico=True)
    isolated=run(FirstBad(),escenarios=ESCENARIOS[:1],modo='aislados',diagnostico=True)
    assert not conv['resultados'][1]['contexto_entrada_conforme_referencia']
    assert not conv['resultados'][1]['decision_documental_correcta']
    assert isolated['resultados'][1]['decision_documental_correcta']
    assert 'SENSITIVE_SENTINEL' not in json.dumps(conv)


def test_diagnostico_opcional_y_sin_mensajes_o_respuestas():
    simple=run()
    detailed=run(diagnostico=True)
    assert not any('diagnostico' in row for row in simple['resultados'])
    text=json.dumps(detailed,ensure_ascii=False)
    for sc in ESCENARIOS:
        for t in sc.turnos:assert t.mensaje not in text
    assert 'output_text' not in text and 'api_key' not in text
    assert detailed['resultados'][0]['diagnostico']['traza']['delta']


@pytest.mark.parametrize('mutation',[
    lambda r:r.update(resultados=[],turnos=0,turnos_programados=0),
    lambda r:r.update(resultados=r['resultados'][:-1]),
    lambda r:r.update(interrumpida=True),
    lambda r:r.update(turnos_no_ejecutados=1),
    lambda r:r['resultados'][0].update(ruta=''),
])
def test_incompletos_y_vacios_no_aprueban(mutation):
    r=run();mutation(r)
    assert not ev.satisfactoria(r)


def test_evaluacion_vacia_no_aprueba():
    r=run(escenarios=())
    assert not r['satisfactoria'] and r['metricas_etapas']['contrato']['tasa'] is None


def test_cli_default_simulado_no_crea_openai(tmp_path,monkeypatch,capsys):
    import app.services.interpretation_service as v22
    import app.services.interpretation_service23 as v23
    def forbidden(**kwargs):pytest.fail('Ningún cliente OpenAI real')
    monkeypatch.setattr(v22,'OpenAI',forbidden);monkeypatch.setattr(v23,'OpenAI',forbidden)
    path=tmp_path/'comparacion.json'
    assert ev.main(['--modo','ambos','--diagnostico','--output',str(path)])==0
    r=json.loads(path.read_text())
    assert r==json.loads(capsys.readouterr().out)
    assert r['satisfactoria'] and r['informes_ejecutados']==r['informes_programados']==4
    assert {x['version_contrato'] for x in r['informes']}=={'2.2',ev.VERSION}
    assert all(x['modalidad']=='simulada' for x in r['informes'])


@pytest.mark.parametrize('key',[None,SecretStr(''),SecretStr(' ')])
def test_cli_real_sin_configuracion_no_crea_servicios(key,monkeypatch,capsys):
    monkeypatch.setattr(settings,'openai_api_key',key)
    def forbidden(*args,**kwargs):pytest.fail('No debe construir servicio')
    monkeypatch.setattr(ev,'crear_servicio',forbidden)
    assert ev.main(['--real'])==2
    assert 'no ejecutada' in capsys.readouterr().err


def test_cli_interrumpido_no_aprueba_versiones_no_ejecutadas(monkeypatch,capsys):
    class Timeout(ev.ProveedorComparativo):
        def create(self,**kwargs):raise TimeoutError('SENSITIVE_SENTINEL')
    monkeypatch.setattr(ev,'ProveedorComparativo',Timeout)
    assert ev.main(['--simulated','--modo','ambos'])==1
    r=json.loads(capsys.readouterr().out)
    assert not r['satisfactoria'] and r['informes_programados']==4 and r['informes_ejecutados']==1
    assert 'SENSITIVE_SENTINEL' not in json.dumps(r)


def test_modalidades_y_proveedores_incompatibles_no_se_inventan():
    with pytest.raises(ValueError):ev.crear_servicio('otra')
    with pytest.raises(ValueError):ev.evaluar_comparativo(None,version=ev.VERSION,modalidad='real',simulado=object())
    with pytest.raises(ValueError):ev.evaluar_comparativo(None,version=ev.VERSION,modalidad='simulada')


def test_rubrica_no_exige_tema_auxiliar_que_no_figura_como_critico():
    class WithoutAuxiliaryTopic(ev.ProveedorComparativo):
        def create(self,**kwargs):
            self.salida=deepcopy(self.salida)
            if self.salida['objetivo']['referente']=='otro':
                self.salida['tema']=InterpretacionCandidata.model_validate(p()).tema.model_dump()
            return super().create(**kwargs)
    r=run(WithoutAuxiliaryTopic(),escenarios=(ESCENARIOS[3],))
    row=r['resultados'][1]
    assert row['interpretacion_semantica_correcta'] and row['decision_documental_correcta']
    assert not row['equivalencia_completa_fixture']  # La diferencia no se oculta.


def test_rubrica_no_equipara_negacion_procedencia_o_aceptacion():
    class ObservedRenewal(ev.ProveedorComparativo):
        def create(self,**kwargs):
            self.salida=deepcopy(self.salida)
            self.salida['operaciones']['renovacion']['observacion']=self.salida['operaciones']['renovacion']['solicitud']
            self.salida['operaciones']['renovacion']['solicitud']=None
            return super().create(**kwargs)
    r=run(ObservedRenewal(),escenarios=ESCENARIOS[:1])
    assert not r['resultados'][0]['interpretacion_semantica_correcta']
    assert not r['resultados'][0]['ruta']
