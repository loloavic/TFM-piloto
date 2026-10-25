"""Normalizadores de sintaxis explícitos; no resuelven contexto ni eligen corpus."""
from dataclasses import dataclass
from typing import Literal
from pydantic import BaseModel, ConfigDict

from app.graph.interpretation_contract import EvidenciaInterpretada, InterpretacionTurno, Motivo
from app.graph.interpretation_candidate import InterpretacionCandidata


class ObjetivoDelta(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', frozen=True, revalidate_instances='always')
    identificacion: Literal['no_mencionado', 'explicito_unico', 'referencia_contextual', 'multiple', 'ambiguo'] = 'no_mencionado'
    referente: Literal['ninguno', 'actual', 'otro'] = 'ninguno'
    neutral: bool = False


class DeltaCanonico(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', frozen=True, revalidate_instances='always')
    objetivo: ObjetivoDelta = ObjetivoDelta()
    evidencias: tuple[EvidenciaInterpretada, ...] = ()
    faltantes: tuple[Motivo, ...] = ()
    contradicciones: tuple[Motivo, ...] = ()
    incertidumbre_relacion: bool = False


def normalizar_v22(model: InterpretacionTurno) -> DeltaCanonico:
    checked = InterpretacionTurno.model_validate(model.model_dump())
    # El evento explícito titular legado se conserva como tal. Nunca derivar
    # identificación desde relación o edad, ni inventar un valor de titular.
    holders = [e for e in checked.evidencias if e.dimension == 'titular'
               and e.origen == 'explicito_turno' and e.sujeto == 'objetivo'
               and e.acto != 'negacion' and e.valor != 'desconocido']
    unique = len({e.valor for e in holders}) == 1 and 'titular' not in checked.contradicciones
    goal = ObjetivoDelta(identificacion='explicito_unico' if unique else 'no_mencionado')
    return DeltaCanonico(objetivo=goal, evidencias=tuple(checked.evidencias),
                         faltantes=tuple(checked.faltantes),
                         contradicciones=tuple(checked.contradicciones))


def normalizar_candidata(model: InterpretacionCandidata) -> DeltaCanonico:
    checked = InterpretacionCandidata.model_validate(model.model_dump())
    events = []
    conflicts = set()
    info_relation = False
    reasons = {'ambito': 'tramite', 'tema': 'tramite', 'edad': 'edad',
               'dni_previo': 'dni_previo', 'funcion_documento': 'documento'}
    for name in ('ambito', 'tema', 'edad', 'dni_previo', 'funcion_documento', 'relacion'):
        fact = getattr(checked, name)
        if fact.estado in {'no_mencionado', 'no_aplicable'}:
            continue
        subject = {'objetivo': 'objetivo', 'acompanante': 'otro', 'no_resuelto': 'no_resuelto'}[fact.sujeto]
        if fact.estado in {'incierto', 'contradictorio'}:
            if name == 'relacion' and subject == 'objetivo' and fact.estado == 'incierto':
                info_relation = True  # No selecciona persona; materialidad en política.
            elif subject != 'otro':
                conflicts.add('titular' if subject == 'no_resuelto' else reasons.get(name, 'titular'))
            continue
        events.append(EvidenciaInterpretada(dimension=name, valor=fact.valor,
            acto=fact.acto, origen=fact.origen, sujeto=subject))
    acts = {'solicitud': 'solicitud_afirmativa', 'negacion': 'negacion',
            'observacion': 'observacion', 'aclaracion': 'aclaracion'}
    for operation in ('primera_vez', 'renovacion', 'duplicado'):
        for source, act in acts.items():
            support = getattr(getattr(checked.operaciones, operation), source)
            if support is not None:
                events.append(EvidenciaInterpretada(dimension='operacion', valor=operation,
                    acto=act, origen=support.origen,
                    sujeto={'objetivo': 'objetivo', 'acompanante': 'otro', 'no_resuelto': 'no_resuelto'}[support.sujeto]))
    return DeltaCanonico(objetivo=ObjetivoDelta(**checked.objetivo.model_dump(), neutral=True),
        evidencias=tuple(events), contradicciones=tuple(sorted(conflicts)),
        incertidumbre_relacion=info_relation)


@dataclass(frozen=True)
class SeleccionObjetivo:
    # Prueba neutral interna; no contiene categoría demográfica ni familiar.
    valor: Literal['identificado'] = 'identificado'
    acto: Literal['solicitud_afirmativa', 'negacion', 'observacion', 'aclaracion'] = 'observacion'


@dataclass(frozen=True)
class ReferenciaObjetivo:
    valor: Literal['actual', 'otro']
