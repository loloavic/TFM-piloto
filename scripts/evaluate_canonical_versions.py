"""Solo fixtures: ejecuta normalizadores y política real; nunca usa un LLM."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.graph.canonical_adapter import adaptar_contrato
from scripts.v2_interpretation_scenarios import ESCENARIOS
from scripts.v23_interpretation_scenarios import CASES


def _apply(context, payload, version):
    return adaptar_contrato(context, dict(turno=context['turno'] + 1 if context else 1,
        revision=context['revision'] if context else 0), payload, version=version)


def evaluar_version(version, *, modo='conversacion', diagnostico=False):
    if version not in {'2.2', '2.3-candidata-1'} or modo not in {'conversacion','aislados'}:
        raise ValueError('modalidad_no_admitida')
    rows = []
    for scenario in ESCENARIOS:
        payloads = ([t.salida_simulada for t in scenario.turnos] if version=='2.2'
                    else CASES[scenario.codigo])
        # Prefijos construidos por la política real, no decisiones documentales
        # simuladas. Las expectativas de ruta originales solo puntúan el resultado.
        reference = None
        before = []
        for payload in payloads:
            before.append(reference)
            reference = _apply(reference, payload, version).contexto_canonico
        context = None
        for index, (payload, expected) in enumerate(zip(payloads,scenario.turnos),1):
            if modo=='aislados':context=before[index-1]
            result = _apply(context,payload,version)
            context=result.contexto_canonico
            outcome = ('abstencion' if context['ambito']=='fuera_alcance' else
                'aclaracion' if context['pendientes'] else 'documentada' if result.ruta else 'abstencion')
            row=dict(escenario=scenario.codigo,turno=index,codigo=result.codigo,
                     ruta=result.ruta,ruta_esperada=expected.ruta_esperada,
                     decision=outcome,decision_esperada=expected.decision_esperada,
                     correcta=result.codigo=='ok' and result.ruta==expected.ruta_esperada
                         and outcome==expected.decision_esperada)
            if diagnostico:row['traza']=result.traza
            rows.append(row)
    positives=[r for r in rows if r['ruta_esperada']]
    return dict(version=version,modalidad='fixtures_sin_llm',modo=modo,turnos=len(rows),
                positivas_esperadas=len(positives),
                positivas_autorizadas=sum(bool(r['ruta']) and r['ruta']==r['ruta_esperada'] for r in positives),
                autorizaciones_incorrectas=sum(bool(r['ruta']) and r['ruta']!=r['ruta_esperada'] for r in rows),
                correctas=sum(r['correcta'] for r in rows),
                satisfactoria=len(rows)==29 and all(r['correcta'] for r in rows),resultados=rows)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version',choices=('2.2','2.3-candidata-1'),required=True)
    parser.add_argument('--modo',choices=('conversacion','aislados'),default='conversacion')
    parser.add_argument('--diagnostico',action='store_true')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args(argv)
    report=evaluar_version(args.version,modo=args.modo,diagnostico=args.diagnostico)
    encoded=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    if args.output:args.output.write_text(encoded,encoding='utf-8')
    print(encoded,end='')
    return 0 if report['satisfactoria'] else 1


if __name__=='__main__':raise SystemExit(main())
