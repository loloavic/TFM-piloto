"""Comparación 2.2/2.3. Fixtures por defecto; --real es opt-in facturable."""
import argparse
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
import json
from math import ceil
from pathlib import Path
import sys
from types import SimpleNamespace
from time import perf_counter

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))

from app.core.config import settings
from app.graph.canonical_adapter import adaptar_contrato, _traza
from app.graph.canonical_delta import normalizar_candidata, normalizar_v22
from app.graph.context_policy import contexto_inicial, ruta_documental
from app.graph.interpretation_diagnostics import condiciones_documentales
from app.graph.interpretation_candidate import InterpretacionCandidata
from app.graph.interpretation_contract import InterpretacionTurno
from app.services.interpretation_service import InterpretationService
from app.services.interpretation_service import INSTRUCCIONES as PROMPT22, esquema_estricto as SCHEMA22
from app.services.interpretation_service23 import InterpretationService23, VERSION, INSTRUCCIONES as PROMPT23, esquema_estricto23
from scripts.v2_interpretation_scenarios import ESCENARIOS
from scripts.v23_interpretation_scenarios import CASES
from scripts.v2_evaluation_diagnostics import evaluar_etapas,clave_semantica,contexto_comparable

TECHNICAL={'error_proveedor','timeout','sin_configuracion','registro_inseguro',
           'error_interprete','entrada_invalida','version_estado_incompatible','conflicto_contexto'}


class ProveedorComparativo:
    def __init__(self):self.responses=self;self.salida=None
    def create(self,**kwargs):
        return SimpleNamespace(status='completed',output=[],usage=None,output_text=json.dumps(self.salida))
    def close(self):pass


def crear_servicio(version,client=None):
    if version=='2.2':return InterpretationService(client=client)
    if version==VERSION:return InterpretationService23(client=client)
    raise ValueError('version_no_admitida')


def _apply(c,payload,version):
    return adaptar_contrato(c,dict(turno=c['turno']+1 if c else 1,
                                  revision=c['revision'] if c else 0),payload,version=version)


def _goal_equivalent(actual,expected,before):
    if actual.identificacion!=expected.identificacion:return False
    if actual.referente==expected.referente:return True
    # Referencia local actual de una identificación explícita nueva (C1).
    return (expected.identificacion=='explicito_unico' and expected.referente=='ninguno'
            and actual.referente=='actual' and (not before or
            before.get('objetivo',{}).get('estado')!='confirmado'))


def etapas23(result,gold,turn,before,reference,age_inherited=False):
    valid=result.interpretacion is not None
    actual=normalizar_candidata(result.interpretacion) if valid else None
    expected=normalizar_candidata(gold)
    observed={clave_semantica(e.model_dump(),before) for e in actual.evidencias} if valid else set()
    required={clave_semantica(e.model_dump(),before) for e in expected.evidencias}
    # Mismas dimensiones críticas de la rúbrica original. Los fixtures completos
    # incluyen convenciones auxiliares; no convertirlas en requisitos semánticos.
    dimensions={e['dimension'] for e in turn.evidencias_esperadas}
    critical=set()
    for e in expected.evidencias:
        if e.dimension in dimensions or e.dimension=='relacion' and 'titular' in dimensions:
            critical.add(clave_semantica(e.model_dump(),before))
    goal_required=bool(dimensions & {'titular','referencia_titular'})
    goal_ok=valid and (not goal_required or _goal_equivalent(actual.objetivo,expected.objetivo,before))
    uncertain_ok=True
    for dimension in dimensions & {'edad','ambito','tema','dni_previo','funcion_documento','relacion'}:
        expected_fact=getattr(gold,dimension)
        if expected_fact.estado in {'incierto','contradictorio'}:
            observed_fact=getattr(result.interpretacion,dimension) if valid else None
            uncertain_ok &= bool(observed_fact is not None and observed_fact.model_dump()==expected_fact.model_dump())
    semantic=bool(valid and result.estado=='ok' and goal_ok and critical<=observed and uncertain_ok)
    full=bool(semantic and observed==required and
        _goal_equivalent(actual.objetivo,expected.objetivo,before) and
        actual.contradicciones==expected.contradicciones and
        actual.incertidumbre_relacion==expected.incertidumbre_relacion)
    after=result.contexto_canonico;ref_after=reference['despues']
    age_now=bool(full and any(e.dimension=='edad' and e.origen=='explicito_turno' for e in actual.evidencias)
                 and after['edad']['turno']==after['turno']
                 and ref_after['edad']['turno']==ref_after['turno'])
    age_kept=bool(age_inherited and before and reference['antes'] and
                  before['edad']==after['edad'] and reference['antes']['edad']==ref_after['edad'])
    normalize=age_now or age_kept
    input_ok=(contexto_comparable(before,normalizar_edad=age_inherited)==
              contexto_comparable(reference['antes'],normalizar_edad=age_inherited))
    transition=(contexto_comparable(after,normalizar_edad=normalize)==
                contexto_comparable(ref_after,normalizar_edad=normalize))
    return dict(interpretacion_semantica_correcta=semantic,equivalencia_completa_fixture=full,
        transicion_canonica_correcta=transition,contexto_entrada_conforme_referencia=input_ok,
        interpretacion_semantica_evaluable=valid,transicion_evaluable=bool(valid and full and input_ok),
        edad_origen_equivalente=normalize)


def decision(c):
    return ('abstencion' if c['ambito']=='fuera_alcance' else 'aclaracion' if c['pendientes']
            else 'documentada' if ruta_documental(c) else 'abstencion')


def satisfactoria(report):
    rows=report.get('resultados',[])
    return bool(report.get('turnos_programados',0)>0 and not report.get('interrumpida',True)
        and report.get('turnos_no_ejecutados')==0 and len(rows)==report['turnos_programados']
        and report.get('turnos')==len(rows) and all(
            all(r.get(k) is True for k in ('contrato_valido','interpretacion_semantica_correcta',
                'transicion_canonica_correcta','decision_documental_correcta'))
            and r['ruta']==r['ruta_esperada'] and r['decision']==r['decision_esperada'] for r in rows))


def evaluar_comparativo(service,*,version,modalidad,modo='conversacion',simulado=None,escenarios=ESCENARIOS,diagnostico=False):
    if (version not in {'2.2',VERSION} or modalidad not in {'simulada','real'}
            or modo not in {'conversacion','aislados'}):raise ValueError('modalidad_no_admitida')
    if (modalidad=='simulada')!=(simulado is not None):raise ValueError('proveedor_modalidad_incompatible')
    escenarios=tuple(escenarios)
    rows=[];interrupted=False;planned=sum(len(s.turnos) for s in escenarios)
    planned_positives=sum(bool(t.ruta_esperada) for s in escenarios for t in s.turnos)
    for scenario in escenarios:
        raw=([t.salida_simulada for t in scenario.turnos] if version=='2.2' else CASES[scenario.codigo])
        if len(raw)!=len(scenario.turnos):raise ValueError('matriz_incompatible')
        model=InterpretacionTurno if version=='2.2' else InterpretacionCandidata
        golds=[model.model_validate(p) for p in raw]
        refs=[];reference_context=None
        for gold in golds:
            previous=deepcopy(reference_context)
            reference_context=_apply(reference_context,gold.model_dump(),version).contexto_canonico
            refs.append(dict(antes=previous,despues=deepcopy(reference_context)))
        context=None;age_equivalent=False
        for index,(turn,gold,reference) in enumerate(zip(scenario.turnos,golds,refs),1):
            if modo=='aislados':context=deepcopy(reference['antes']);age_equivalent=False
            before=deepcopy(context)
            if simulado is not None:simulado.salida=gold.model_dump()
            started=perf_counter()
            result=service.interpretar(turn.mensaje,context,diagnostico=diagnostico)
            metrics=asdict(result.metricas)
            metrics['latencia_ms']=round((perf_counter()-started)*1000,3)
            context=result.contexto_canonico
            if version=='2.2':
                stages=evaluar_etapas(result,turn,before,reference,edad_heredada_equivalente=age_equivalent)
                evaluated=result.estado in {'ok','respuesta_invalida'}
                validation=(result.diagnostico or {}).get('errores_validacion',[])
            else:
                stages=etapas23(result,gold,turn,before,reference,age_equivalent)
                evaluated=result.codigo_validacion!='no_evaluado'
                validation=[] if result.codigo_validacion in {'ok','no_evaluado'} else [result.codigo_validacion]
            age_equivalent=stages['edad_origen_equivalente']
            route=ruta_documental(context);outcome=decision(context)
            rows.append(dict(escenario=scenario.codigo,turno=index,estado_proveedor=result.estado,
                estado_interpretacion=result.estado_interpretacion,codigos_validacion=validation,
                contrato_valido=result.interpretacion is not None,contrato_evaluable=evaluated,
                ruta=route,ruta_esperada=turn.ruta_esperada,decision=outcome,decision_esperada=turn.decision_esperada,
                decision_documental_correcta=route==turn.ruta_esperada and outcome==turn.decision_esperada,
                autorizacion_incorrecta=bool(route) and route!=turn.ruta_esperada,
                aclaracion_necesaria=turn.decision_esperada=='aclaracion',
                aclaracion_necesaria_atendida=turn.decision_esperada=='aclaracion' and outcome=='aclaracion',
                aclaracion_innecesaria=turn.decision_esperada!='aclaracion' and outcome=='aclaracion',
                **stages,**metrics))
            if diagnostico:
                if version==VERSION:
                    trace=result.transicion.traza
                else:
                    trace=_traza(before or contexto_inicial(),context)
                    trace['delta']=(normalizar_v22(result.interpretacion).model_dump(mode='json')
                                    if result.interpretacion is not None else None)
                rows[-1]['diagnostico']=dict(traza=trace,
                    codigo_adaptacion=result.transicion.codigo if version==VERSION else None,
                    condiciones_documentales=condiciones_documentales(context))
            if result.estado in TECHNICAL:interrupted=True;break
        if interrupted:break
    def metric(key,eligible=None):
        data=[r for r in rows if eligible is None or r[eligible]]
        count=sum(r[key] for r in data)
        return dict(correctos=count,evaluables=len(data),tasa=count/len(data) if data else None)
    prompt= PROMPT22 if version=='2.2' else PROMPT23
    schema= SCHEMA22() if version=='2.2' else esquema_estricto23()
    latency=sorted(r['latencia_ms'] for r in rows);n=len(rows)
    report=dict(version_evaluacion='v2.2g-1',version_contrato=version,modalidad=modalidad,modo=modo,
        diagnostico=diagnostico,alcance_latencia='servicio_completo_sin_rubrica',
        rubrica='criticos_v2.2c_y_correspondencia_23_v1',
        modelo=settings.openai_model if modalidad=='real' else 'fixture_sin_llm',
        huella_prompt=sha256(prompt.encode()).hexdigest(),
        huella_esquema=sha256(json.dumps(schema,sort_keys=True).encode()).hexdigest(),
        turnos_programados=planned,turnos=n,turnos_no_ejecutados=planned-n,interrumpida=interrupted,
        metricas_etapas=dict(contrato=metric('contrato_valido','contrato_evaluable'),
            entrega_contrato_valido=metric('contrato_valido'),
            interpretacion_semantica=metric('interpretacion_semantica_correcta','interpretacion_semantica_evaluable'),
            transicion_controlada=metric('transicion_canonica_correcta','transicion_evaluable'),
            decision_documental=metric('decision_documental_correcta')),
        cobertura_documental=dict(positivas_esperadas=planned_positives,
            positivas_autorizadas=sum(bool(r['ruta']) and r['ruta']==r['ruta_esperada'] for r in rows if r['ruta_esperada']),
            autorizaciones_incorrectas=sum(r['autorizacion_incorrecta'] for r in rows),
            aclaraciones_necesarias=sum(r['aclaracion_necesaria'] for r in rows),
            aclaraciones_atendidas=sum(r['aclaracion_necesaria_atendida'] for r in rows),
            aclaraciones_innecesarias=sum(r['aclaracion_innecesaria'] for r in rows)),
        latencia_p50_ms=latency[ceil(n*.5)-1] if n else None,
        latencia_p95_ms=latency[ceil(n*.95)-1] if n else None,
        tokens_entrada=sum(r['tokens_entrada'] for r in rows),tokens_salida=sum(r['tokens_salida'] for r in rows),
        resultados=rows)
    report['satisfactoria']=satisfactoria(report)
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--real',action='store_true',help='Autoriza llamadas facturables: 29 por versión/modalidad')
    mode.add_argument('--simulated',action='store_true')
    parser.add_argument('--version',choices=('2.2',VERSION,'ambas'),default='ambas')
    parser.add_argument('--modo',choices=('conversacion','aislados','ambos'),default='conversacion')
    parser.add_argument('--diagnostico',action='store_true',help='Añade categorías validadas y pendientes, nunca transcripciones')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args(argv)
    if args.real and (not settings.openai_api_key or not settings.openai_api_key.get_secret_value().strip()
                      or not settings.openai_model.strip()):
        print('Evaluación real no ejecutada: falta configuración OpenAI válida.',file=sys.stderr);return 2
    reports=[]
    for version in (('2.2',VERSION) if args.version=='ambas' else (args.version,)):
        for mode_name in (('conversacion','aislados') if args.modo=='ambos' else (args.modo,)):
            fake=None if args.real else ProveedorComparativo()
            service=crear_servicio(version,client=fake)
            try:report=evaluar_comparativo(service,version=version,
                    modalidad='real' if args.real else 'simulada',modo=mode_name,simulado=fake,diagnostico=args.diagnostico)
            finally:service.close()
            reports.append(report)
            if report['interrumpida']:break
        if reports[-1]['interrumpida']:break
    expected=(2 if args.version=='ambas' else 1)*(2 if args.modo=='ambos' else 1)
    success=len(reports)==expected and all(satisfactoria(r) for r in reports)
    output=dict(informes_programados=expected,informes_ejecutados=len(reports),satisfactoria=success,informes=reports)
    encoded=json.dumps(output,ensure_ascii=False,indent=2)+'\n'
    if args.output:args.output.write_text(encoded,encoding='utf-8')
    print(encoded,end='')
    return 0 if success else 1


if __name__=='__main__':raise SystemExit(main())
