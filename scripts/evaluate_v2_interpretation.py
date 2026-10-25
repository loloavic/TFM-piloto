"""Evaluación V2 separada de la app. Por defecto: fixtures, cero llamadas reales."""
import argparse
from dataclasses import asdict
from copy import deepcopy
from hashlib import sha256
import json
from math import ceil
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings
from app.graph.context_policy import ruta_documental
from app.services.interpretation_service import (
    InterpretationService, PROMPT_VERSION, INSTRUCCIONES, esquema_estricto,
)
from scripts.v2_interpretation_scenarios import ESCENARIOS
from scripts.v2_evaluation_diagnostics import cargar_referencias, evaluar_etapas, diagnostico_turno


class ProveedorSimulado:
    """Reproduce fixtures; nunca llama al SDK ni interpreta el lenguaje."""
    def __init__(self):
        self.responses = self
        self.salida = None

    def create(self, **kwargs):
        from types import SimpleNamespace
        return SimpleNamespace(status='completed', output=[], usage=None,
                               output_text=json.dumps(self.salida))

    def close(self):
        pass


def decision(contexto):
    if contexto['ambito'] == 'fuera_alcance':
        return 'abstencion'
    if contexto['pendientes']:
        return 'aclaracion'
    return 'documentada' if ruta_documental(contexto) else 'abstencion'


def _atom_key(atom):
    return tuple(atom[k] for k in ('dimension', 'valor', 'acto', 'origen', 'sujeto'))


def evaluar(service, *, modalidad, escenarios=ESCENARIOS, simulado=None,
            diagnostico=False, modo_turnos='conversacion'):
    if modalidad not in {'simulada', 'real'}:
        raise ValueError('modalidad_invalida')
    if (modalidad == 'simulada') != (simulado is not None):
        raise ValueError('proveedor_modalidad_incompatible')
    if modo_turnos not in {'conversacion', 'aislados'}:
        raise ValueError('modo_turnos_invalido')
    references = cargar_referencias()
    rows = []
    interrupted = False
    planned = sum(len(e.turnos) for e in escenarios)
    for escenario in escenarios:
        contexto = None  # Aislamiento entre conversaciones; solo un canónico por caso.
        age_equivalent = False  # Prueba de equivalencia de rúbrica, no estado operativo.
        for index, turno in enumerate(escenario.turnos, 1):
            reference = references.get(f'{escenario.codigo}/{index}')
            if modo_turnos == 'aislados':
                if reference is None:
                    raise ValueError('contexto_referencia_ausente')
                contexto = deepcopy(reference['antes'])
                age_equivalent = False
            before = deepcopy(contexto)
            if simulado is not None:
                simulado.salida = turno.salida_simulada
            result = service.interpretar(turno.mensaje, contexto, diagnostico=diagnostico)
            contexto = result.contexto_canonico
            route = ruta_documental(contexto)
            observed = decision(contexto)
            atoms = ({_atom_key(e.model_dump()) for e in result.interpretacion.evidencias}
                     if result.interpretacion is not None else set())
            semantic = (result.estado == 'ok' and
                        {_atom_key(a) for a in turno.evidencias_esperadas} <= atoms and
                        all((contexto[dim] if dim == 'ambito' else contexto[dim]['valor']) == value
                            for dim, value in turno.canonico_esperado))
            etapas = evaluar_etapas(result, turno, before, reference,
                                    edad_heredada_equivalente=age_equivalent)
            age_equivalent = etapas['edad_origen_equivalente']
            documental = route == turno.ruta_esperada and observed == turno.decision_esperada
            expected_clarification = turno.decision_esperada == 'aclaracion'
            incorrect_route = bool(route) and route != turno.ruta_esperada
            rows.append(dict(
                escenario=escenario.codigo, categoria=escenario.categoria, turno=index,
                estado_proveedor=result.estado, estado_contrato=result.estado_interpretacion,
                contrato_valido=result.interpretacion is not None,
                contrato_evaluable=result.estado in {'ok', 'respuesta_invalida'},
                clasificacion_correcta=semantic,
                ruta_esperada=turno.ruta_esperada, ruta_obtenida=route,
                ruta_correcta=route == turno.ruta_esperada,
                ruta_incorrectamente_autorizada=incorrect_route,
                decision_esperada=turno.decision_esperada, decision_obtenida=observed,
                aclaracion_necesaria=expected_clarification,
                aclaracion_necesaria_atendida=expected_clarification and observed == 'aclaracion',
                aclaracion_necesaria_omitida=expected_clarification and observed != 'aclaracion',
                aclaracion_innecesaria=not expected_clarification and observed == 'aclaracion',
                abstencion=observed == 'abstencion',
                abstencion_correcta=observed == 'abstencion' and turno.decision_esperada == 'abstencion',
                **asdict(result.metricas), **etapas,
                decision_documental_correcta=documental,
            ))
            if diagnostico:
                rows[-1]['diagnostico'] = diagnostico_turno(result, before, reference, etapas, documental)
            if result.estado in {'error_proveedor', 'timeout', 'sin_configuracion', 'registro_inseguro', 'error_interprete'}:
                interrupted = True
                break
        if interrupted:
            break
    count = len(rows)
    latency = sorted(row['latencia_ms'] for row in rows)
    sums = {name: sum(row[name] for row in rows) for name in (
        'clasificacion_correcta', 'contrato_valido', 'ruta_correcta',
        'ruta_incorrectamente_autorizada', 'aclaracion_necesaria',
        'aclaracion_necesaria_atendida', 'aclaracion_necesaria_omitida',
        'aclaracion_innecesaria', 'abstencion', 'abstencion_correcta',
        'tokens_entrada', 'tokens_salida', 'interpretacion_semantica_correcta',
        'transicion_canonica_correcta', 'decision_documental_correcta',
        'contexto_entrada_conforme_referencia')}
    report = dict(version_evaluacion='v2.2d-1', version_prompt=PROMPT_VERSION,
                version_rubrica='v2.2c-1', modo_turnos=modo_turnos, diagnostico=diagnostico,
                huella_referencias=sha256(json.dumps(references,sort_keys=True).encode()).hexdigest(),
                turnos_programados=planned,
                huella_prompt=sha256(INSTRUCCIONES.encode()).hexdigest(),
                huella_esquema=sha256(json.dumps(esquema_estricto(), sort_keys=True).encode()).hexdigest(),
                modelo=settings.openai_model if modalidad == 'real' else 'fixture_sin_llm',
                modalidad=modalidad, conversaciones=len({r['escenario'] for r in rows}),
                conversaciones_programadas=len(escenarios), turnos=count,
                turnos_no_ejecutados=planned - count, interrumpida=interrupted,
                resumen=dict(**sums,
                    tasa_clasificacion_correcta=sums['clasificacion_correcta'] / count if count else None,
                    latencia_p50_ms=latency[ceil(count * .5) - 1] if count else None,
                    latencia_p95_ms=latency[ceil(count * .95) - 1] if count else None),
                resultados=rows)
    def stage_metric(key, eligibility=None):
        eligible = [r for r in rows if eligibility is None or r[eligibility]]
        correct = sum(r[key] for r in eligible)
        return dict(correctos=correct, evaluables=len(eligible),
                    tasa=correct / len(eligible) if eligible else None)
    report['metricas_etapas'] = {
        'contrato': stage_metric('contrato_valido', 'contrato_evaluable'),
        'entrega_contrato_valido': stage_metric('contrato_valido'),
        'equivalencia_completa_fixture': stage_metric('equivalencia_completa_fixture',
                                                      'interpretacion_semantica_evaluable'),
        'interpretacion_semantica': stage_metric('interpretacion_semantica_correcta',
                                                'interpretacion_semantica_evaluable'),
        'transicion_controlada': stage_metric('transicion_canonica_correcta', 'transicion_evaluable'),
        'decision_documental': stage_metric('decision_documental_correcta'),
    }
    positives = [r for r in rows if r['ruta_esperada']]
    report['cobertura_documental'] = {
        'positivas_esperadas': len(positives),
        'positivas_correctamente_autorizadas': sum(bool(r['ruta_obtenida']) and r['ruta_correcta'] for r in positives),
        'autorizaciones_totales': sum(bool(r['ruta_obtenida']) for r in rows),
        'autorizaciones_incorrectas': sums['ruta_incorrectamente_autorizada'],
    }
    report['satisfactoria'] = evaluacion_satisfactoria(report)
    return report


def evaluacion_satisfactoria(report):
    rows = report.get('resultados', [])
    count = report.get('turnos_programados', 0)
    return bool(count > 0 and len(rows) == count and report.get('turnos') == count
        and report.get('turnos_no_ejecutados') == 0 and not report.get('interrumpida', True)
        and all(all(row.get(key) is True for key in (
            'contrato_valido', 'interpretacion_semantica_correcta',
            'transicion_canonica_correcta', 'decision_documental_correcta'))
            and row.get('ruta_obtenida') == row.get('ruta_esperada')
            and row.get('decision_obtenida') == row.get('decision_esperada') for row in rows))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--real', action='store_true', help='Autoriza llamadas OpenAI facturables al modelo configurado')
    mode.add_argument('--simulated', action='store_true', help='Fixtures sin red (modo por defecto)')
    parser.add_argument('--diagnostico', action='store_true', help='Añade trazas categóricas por etapa')
    parser.add_argument('--modo-turnos', choices=('conversacion', 'aislados'), default='conversacion')
    parser.add_argument('--output', type=Path, help='Informe JSON: solo categorías y métricas, sin transcripciones')
    args = parser.parse_args(argv)
    if args.real and (not settings.openai_api_key or
                      not settings.openai_api_key.get_secret_value().strip() or
                      not settings.openai_model.strip()):
        print('Evaluación real no ejecutada: falta configuración OpenAI válida.', file=sys.stderr)
        return 2
    fake = None if args.real else ProveedorSimulado()
    service = InterpretationService(client=fake)
    try:
        report = evaluar(service, modalidad='real' if args.real else 'simulada', simulado=fake,
                         diagnostico=args.diagnostico, modo_turnos=args.modo_turnos)
    finally:
        service.close()
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.write_text(encoded, encoding='utf-8')
    print(encoded, end='')
    # Un proveedor roto o una regresión semántica no se ocultan detrás de exit 0.
    return 0 if evaluacion_satisfactoria(report) else 1


if __name__ == '__main__':
    raise SystemExit(main())
