"""Evaluación V2 separada de la app. Por defecto: fixtures, cero llamadas reales."""
import argparse
from dataclasses import asdict
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


def evaluar(service, *, modalidad, escenarios=ESCENARIOS, simulado=None):
    if modalidad not in {'simulada', 'real'}:
        raise ValueError('modalidad_invalida')
    if (modalidad == 'simulada') != (simulado is not None):
        raise ValueError('proveedor_modalidad_incompatible')
    rows = []
    interrupted = False
    planned = sum(len(e.turnos) for e in escenarios)
    for escenario in escenarios:
        contexto = None  # Aislamiento entre conversaciones; solo un canónico por caso.
        for index, turno in enumerate(escenario.turnos, 1):
            if simulado is not None:
                simulado.salida = turno.salida_simulada
            result = service.interpretar(turno.mensaje, contexto)
            contexto = result.contexto_canonico
            route = ruta_documental(contexto)
            observed = decision(contexto)
            atoms = ({_atom_key(e.model_dump()) for e in result.interpretacion.evidencias}
                     if result.interpretacion is not None else set())
            semantic = (result.estado == 'ok' and
                        {_atom_key(a) for a in turno.evidencias_esperadas} <= atoms and
                        all((contexto[dim] if dim == 'ambito' else contexto[dim]['valor']) == value
                            for dim, value in turno.canonico_esperado))
            expected_clarification = turno.decision_esperada == 'aclaracion'
            incorrect_route = bool(route) and route != turno.ruta_esperada
            rows.append(dict(
                escenario=escenario.codigo, categoria=escenario.categoria, turno=index,
                estado_proveedor=result.estado, estado_contrato=result.estado_interpretacion,
                contrato_valido=result.interpretacion is not None,
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
                **asdict(result.metricas),
            ))
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
        'tokens_entrada', 'tokens_salida')}
    return dict(version_evaluacion='v2.2b-1', version_prompt=PROMPT_VERSION,
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--real', action='store_true', help='Autoriza llamadas OpenAI facturables al modelo configurado')
    mode.add_argument('--simulated', action='store_true', help='Fixtures sin red (modo por defecto)')
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
        report = evaluar(service, modalidad='real' if args.real else 'simulada', simulado=fake)
    finally:
        service.close()
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.write_text(encoded, encoding='utf-8')
    print(encoded, end='')
    # Un proveedor roto o una regresión semántica no se ocultan detrás de exit 0.
    return 0 if all(r['clasificacion_correcta'] and r['ruta_correcta'] and
                    r['decision_esperada'] == r['decision_obtenida']
                    for r in report['resultados']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
