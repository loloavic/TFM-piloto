from copy import deepcopy
import json
from types import SimpleNamespace as NS

import pytest

from app.graph.interpretation_diagnostics import diagnosticar_validacion, condiciones_documentales
from app.graph.interpretation_contract import InterpretacionTurno
from app.services.interpretation_service import InterpretationService
from scripts import evaluate_v2_interpretation as ev
from scripts.v2_evaluation_diagnostics import cargar_referencias
from scripts.v2_interpretation_scenarios import ESCENARIOS, atom, packet, request

META = dict(turno=1, revision=0)


def run(fake=None, **kwargs):
    fake = fake or ev.ProveedorSimulado()
    return ev.evaluar(InterpretationService(client=fake), modalidad='simulada', simulado=fake, **kwargs)


@pytest.mark.parametrize('payload,code', [
    ('SENSITIVE_SENTINEL', 'json_invalido'),
    ('{"version":"2.1","version":"2.1"}', 'clave_duplicada'),
    (' ' * 16385, 'limite_excedido'),
    (None, 'tipo_invalido'),
    ({}, 'campo_faltante'),
    (dict(packet(), SENSITIVE_SENTINEL='PRIVATE_VALUE'), 'campo_extra'),
    (packet(atom('edad','SENSITIVE_SENTINEL')), 'valor_no_permitido'),
    (packet(atom('edad','renovacion')), 'dimension_valor_incompatible'),
    (packet(atom('ambito','dni'),atom('ambito','dni')), 'duplicado'),
    (packet(), 'evidencia_vacia'),
])
def test_errores_cerrados_sin_datos_libres(payload, code, caplog):
    codes = diagnosticar_validacion(META, payload)
    assert code in codes
    assert 'SENSITIVE_SENTINEL' not in json.dumps(codes) + caplog.text
    assert 'PRIVATE_VALUE' not in json.dumps(codes)


def test_metadatos_no_se_serializan():
    assert diagnosticar_validacion({'turno':'PRIVATE_VALUE'}, packet()) == ['metadatos_invalidos']


def test_diagnostico_por_defecto_desactivado_y_resultado_identico():
    plain = run()
    detailed = run(diagnostico=True)
    assert plain['satisfactoria'] and detailed['satisfactoria']
    assert all('diagnostico' not in row for row in plain['resultados'])
    for a,b in zip(plain['resultados'],detailed['resultados']):
        assert a['ruta_obtenida'] == b['ruta_obtenida']
        assert a['decision_obtenida'] == b['decision_obtenida']
        assert a['transicion_canonica_correcta'] == b['transicion_canonica_correcta']
        assert b['diagnostico']['etapa_discrepancia'] == 'sin_discrepancia'


def test_informe_no_contiene_mensajes_o_salidas_crudas():
    report = run(diagnostico=True)
    encoded = json.dumps(report, ensure_ascii=False)
    for sc in ESCENARIOS:
        for turn in sc.turnos:
            assert turn.mensaje not in encoded
    assert 'output_text' not in encoded and 'api_key' not in encoded
    for row in report['resultados']:
        for e in row['diagnostico']['evidencias']:
            assert set(e) == {'dimension','valor','acto','origen','sujeto'}
            InterpretacionTurno.model_validate(packet(e))


def test_referencia_actual_localiza_bloqueo_sin_cambiar_politica():
    class Actual(ev.ProveedorSimulado):
        def create(self,**kwargs):
            self.salida = deepcopy(self.salida)
            self.salida['evidencias'].append(atom('referencia_titular','actual'))
            return super().create(**kwargs)
    report = run(Actual(), diagnostico=True, escenarios=ESCENARIOS[:1])
    row = report['resultados'][0]
    assert row['contrato_valido'] and row['interpretacion_semantica_correcta']
    assert not row['transicion_canonica_correcta'] and not row['decision_documental_correcta']
    d = row['diagnostico']
    assert 'referencia_actual_sin_titular_previo' in d['testigos_categoricos']
    assert 'titular' in d['pendientes_despues'] and not d['pendientes_antes']
    assert any(c['condicion']=='sin_pendientes' and not c['cumplida']
               for c in d['condiciones_documentales'])


def test_campos_y_negaciones_conservan_procedencia_en_diagnostico():
    report = run(diagnostico=True)
    negative = next(r for r in report['resultados'] if r['escenario']=='E05' and r['turno']==2)
    assert negative['diagnostico']['evidencias'][0]['acto'] == 'negacion'
    assert negative['diagnostico']['pendientes_despues']['operacion'] == 'faltante'
    followup = next(r for r in report['resultados'] if r['escenario']=='E03')
    age = next(c for c in followup['diagnostico']['condiciones_documentales']
               if c['condicion']=='edad_confirmada')
    assert not age['aplica']


def test_contrato_incompatible_atribuido_sin_payloads(caplog):
    class Bad(ev.ProveedorSimulado):
        def create(self,**kwargs):
            self.salida = packet(atom('edad','renovacion'))
            return super().create(**kwargs)
    row = run(Bad(),diagnostico=True,escenarios=ESCENARIOS[:1])['resultados'][0]
    assert not row['contrato_valido']
    assert row['diagnostico']['etapa_discrepancia']=='contrato'
    assert row['diagnostico']['errores_validacion']==['dimension_valor_incompatible']
    assert row['diagnostico']['evidencias']==[]
    assert caplog.text==''


def test_metricas_no_confunden_equivalencia_con_decision():
    class Equivalent(ev.ProveedorSimulado):
        def create(self,**kwargs):
            self.salida = deepcopy(self.salida)
            for e in self.salida['evidencias']:
                if e['dimension']=='ambito':e['acto']='solicitud_afirmativa'
            return super().create(**kwargs)
    report = run(Equivalent(),diagnostico=True,escenarios=(ESCENARIOS[2],))
    row = report['resultados'][0]
    assert not row['clasificacion_correcta']  # Métrica histórica, se conserva.
    assert row['interpretacion_semantica_correcta'] and row['decision_documental_correcta']
    assert report['satisfactoria']


@pytest.mark.parametrize('field,value', [('acto','negacion'),('origen','referencia_contextual'),
                                       ('sujeto','otro'),('valor','primera_vez')])
def test_no_equivalencia_de_operacion_negacion_procedencia_o_sujeto(field,value):
    class Changed(ev.ProveedorSimulado):
        def create(self,**kwargs):
            self.salida = deepcopy(self.salida)
            for e in self.salida['evidencias']:
                if e['dimension']=='operacion':e[field]=value
            return super().create(**kwargs)
    row=run(Changed(),escenarios=ESCENARIOS[:1])['resultados'][0]
    assert not row['interpretacion_semantica_correcta']


def test_aislados_usan_predefinidos_y_no_arrastran_error():
    class FirstBad(ev.ProveedorSimulado):
        def __init__(self):
            super().__init__(); self.n=0
        def create(self,**kwargs):
            self.n+=1
            if self.n==1:
                self.salida=packet(*request(),atom('dni_previo','desconocido'))
            return super().create(**kwargs)
    conv=run(FirstBad(),diagnostico=True,escenarios=ESCENARIOS[:1])
    isolated=run(FirstBad(),diagnostico=True,modo_turnos='aislados',escenarios=ESCENARIOS[:1])
    assert conv['modo_turnos']=='conversacion' and isolated['modo_turnos']=='aislados'
    assert conv['resultados'][1]['diagnostico']['etapa_discrepancia']=='arrastre_previo'
    assert not conv['resultados'][1]['decision_documental_correcta']
    assert isolated['resultados'][1]['contexto_entrada_conforme_referencia']
    assert isolated['resultados'][1]['decision_documental_correcta']


def test_referencias_cubren_todos_los_turnos_y_son_estaticas():
    references=cargar_referencias()
    assert len(references)==29
    for sc in ESCENARIOS:
        for i,_ in enumerate(sc.turnos,1):
            assert f'{sc.codigo}/{i}' in references
    isolated=run(modo_turnos='aislados')
    assert isolated['satisfactoria'] and isolated['turnos']==29


@pytest.mark.parametrize('mutation', [
    lambda r:r.update(resultados=[],turnos=0,turnos_programados=0),
    lambda r:r.update(resultados=r['resultados'][:-1]),
    lambda r:r.update(interrumpida=True),
    lambda r:r.update(turnos_no_ejecutados=1),
    lambda r:r.update(turnos_programados=30),
    lambda r:r['resultados'][0].update(contrato_valido=False),
])
def test_incompleto_o_vacio_no_puede_aprobar(mutation):
    report=run()
    mutation(report)
    assert not ev.evaluacion_satisfactoria(report)


def test_ejecucion_vacia_no_aprueba():
    report=run(escenarios=())
    assert not report['satisfactoria']
    assert report['metricas_etapas']['contrato']['tasa'] is None


def test_cli_diagnostico_aislado_sin_red(tmp_path,capsys):
    path=tmp_path/'diagnostico.json'
    assert ev.main(['--simulated','--diagnostico','--modo-turnos','aislados','--output',str(path)])==0
    report=json.loads(path.read_text())
    assert report==json.loads(capsys.readouterr().out)
    assert report['modo_turnos']=='aislados' and report['diagnostico']


def test_equivalencia_hecho_edad_se_mantiene_en_repregunta():
    class Equivalent(ev.ProveedorSimulado):
        def create(self,**kwargs):
            self.salida=deepcopy(self.salida)
            for e in self.salida['evidencias']:
                if e['dimension']=='edad' and e['valor']=='menor' and e['acto']=='observacion':
                    e['acto']='solicitud_afirmativa'
            return super().create(**kwargs)
    report=run(Equivalent(),diagnostico=True)
    assert report['satisfactoria']
    assert report['resultados'][1]['contexto_entrada_conforme_referencia']


def test_declaracion_material_extra_no_se_atribuye_solo_a_transicion():
    class Extra(ev.ProveedorSimulado):
        def create(self,**kwargs):
            self.salida=deepcopy(self.salida)
            self.salida['contradicciones']=['edad']
            return super().create(**kwargs)
    row=run(Extra(),diagnostico=True,escenarios=ESCENARIOS[:1])['resultados'][0]
    assert not row['equivalencia_completa_fixture']
    assert row['diagnostico']['etapa_discrepancia']=='interpretacion_o_transicion'
    assert row['diagnostico']['contradicciones_declaradas']==['edad']


def test_servicio_invalido_privacidad_diagnostica(caplog,capsys):
    class Bad(ev.ProveedorSimulado):
        def create(self,**kwargs):
            return NS(status='completed',output=[],usage=None,output_text=json.dumps({
                'SENSITIVE_NAME':'PRIVATE_DNI_12345678','version':'SENSITIVE_KEY'}))
    result=InterpretationService(client=Bad()).interpretar('SENSITIVE_CITIZEN_MESSAGE',diagnostico=True)
    text=json.dumps(result.diagnostico)
    assert 'SENSITIVE' not in text and 'PRIVATE' not in text
    assert result.diagnostico['errores_validacion']
    captured=capsys.readouterr()
    assert not caplog.text and not captured.out and not captured.err


def test_timeout_en_ultimo_turno_no_aprueba_aunque_no_falten_turnos():
    class LastTimeout(ev.ProveedorSimulado):
        def __init__(self):
            super().__init__(); self.n=0
        def create(self,**kwargs):
            self.n+=1
            if self.n==29:raise TimeoutError('SENSITIVE_SENTINEL')
            return super().create(**kwargs)
    report=run(LastTimeout(),diagnostico=True)
    assert report['turnos']==29 and report['turnos_no_ejecutados']==0
    assert report['interrumpida'] and not report['satisfactoria']
    assert 'SENSITIVE_SENTINEL' not in json.dumps(report)


def test_cli_no_considera_exitosa_evaluacion_vacia(monkeypatch,capsys):
    empty=run(escenarios=())
    monkeypatch.setattr(ev,'evaluar',lambda *args,**kwargs:empty)
    assert ev.main(['--simulated'])==1
    assert not json.loads(capsys.readouterr().out)['satisfactoria']


def test_fallo_semantico_separado_de_contrato_valido():
    class Adult(ev.ProveedorSimulado):
        def create(self,**kwargs):
            self.salida=packet(*request(age='adulto'))
            return super().create(**kwargs)
    row=run(Adult(),diagnostico=True,escenarios=ESCENARIOS[:1])['resultados'][0]
    assert row['contrato_valido'] and not row['interpretacion_semantica_correcta']
    assert row['diagnostico']['etapa_discrepancia']=='interpretacion_o_rubrica'


def test_fallo_canonico_con_evidencia_equivalente_es_transicion():
    from dataclasses import replace
    fake=ev.ProveedorSimulado()
    delegate=InterpretationService(client=fake)
    class CorruptTransition:
        def interpretar(self,*args,**kwargs):
            result=delegate.interpretar(*args,**kwargs)
            c=deepcopy(result.contexto_canonico)
            c['pendientes']['edad']='contradiccion'
            return replace(result,contexto_canonico=c)
    report=ev.evaluar(CorruptTransition(),modalidad='simulada',simulado=fake,
                      diagnostico=True,escenarios=ESCENARIOS[:1])
    row=report['resultados'][0]
    assert row['interpretacion_semantica_correcta'] and row['transicion_evaluable']
    assert row['diagnostico']['etapa_discrepancia']=='transicion'
    assert report['metricas_etapas']['transicion_controlada']['tasa']==0


def test_expectativa_documental_erronea_no_se_atribuye_al_llm():
    from dataclasses import replace
    scenario=ESCENARIOS[12]
    wrong_turn=replace(scenario.turnos[0],ruta_esperada='dni_menor_renovacion',
                       decision_esperada='documentada')
    scenario=replace(scenario,turnos=(wrong_turn,))
    row=run(diagnostico=True,escenarios=(scenario,))['resultados'][0]
    assert row['interpretacion_semantica_correcta'] and row['transicion_canonica_correcta']
    assert row['diagnostico']['etapa_discrepancia']=='decision_o_expectativa'


def test_representacion_adicional_se_muestra_aunque_no_cambie_decision():
    class ExtraObservation(ev.ProveedorSimulado):
        def create(self,**kwargs):
            self.salida=deepcopy(self.salida)
            self.salida['evidencias'].append(atom('operacion','renovacion','observacion'))
            return super().create(**kwargs)
    report=run(ExtraObservation(),diagnostico=True,escenarios=ESCENARIOS[:1])
    row=report['resultados'][0]
    assert row['decision_documental_correcta'] and row['transicion_canonica_correcta']
    assert not row['equivalencia_completa_fixture']
    assert row['diagnostico']['etapa_discrepancia']=='representacion_adicional'
