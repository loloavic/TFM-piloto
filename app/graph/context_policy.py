"""Único escritor del contexto: transición pura, sin texto, proveedor ni historial."""
from copy import deepcopy
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.graph.interpretation_contract import InterpretacionTurno

from app.graph.state import ContextoCanonico, DatoContextual, EvidenciaTurno

OPERACIONES = {'primera_vez', 'renovacion', 'duplicado'}
DOCUMENTADOS = {'dni_menor_primera_vez', 'dni_menor_renovacion', 'dni_consulta_estado'}
TEMAS = {'otra', 'coste', 'plazo', 'cita', 'requisitos', 'seguimiento'}
PRIORIDAD = ('titular', 'documento', 'dni_previo', 'contradiccion', 'operacion', 'edad', 'tramite')
VALORES = {'titular': {'descendiente', 'menor', 'adulto', 'propio'},
           'edad': {'menor', 'adulto'}, 'operacion': OPERACIONES}


def dato(valor='', turno=0, revision=0, estado=None, origen=None) -> DatoContextual:
    return {'valor': valor, 'turno': turno, 'revision': revision,
            'estado': estado or ('confirmado' if valor else 'desconocido'),
            'origen': origen or ('explicito' if valor else 'ausente')}


def contexto_inicial(revision=0, turno=0) -> ContextoCanonico:
    return {'turno': turno, 'revision': revision, 'ambito': 'desconocido',
            'titular': dato(revision=revision), 'edad': dato(revision=revision),
            'operacion': dato(revision=revision), 'rechazadas': [], 'pendientes': {},
            'propuesta_operacion': '', 'tema': 'otra', 'consulta_pendiente': '',
            'retomar': '', 'ultima_ruta': ''}


def validar_contexto(c: dict) -> bool:
    """Validación independiente de las etiquetas públicas y del extractor."""
    try:
        if c['ambito'] not in {'dni', 'desconocido', 'fuera_alcance'}:
            return False
        if c['turno'] < 0 or c['revision'] < 0 or c['tema'] not in TEMAS:
            return False
        if c['consulta_pendiente'] not in TEMAS | {''} or c['retomar'] not in TEMAS | {''}:
            return False
        if set(c['rechazadas']) - OPERACIONES or c['propuesta_operacion'] not in OPERACIONES | {''}:
            return False
        if set(c['pendientes']) - set(PRIORIDAD) or set(c['pendientes'].values()) - {'faltante', 'contradiccion'}:
            return False
        for field, allowed in VALORES.items():
            d = c[field]
            if d['revision'] != c['revision'] or not 0 <= d['turno'] <= c['turno']:
                return False
            if d['valor'] not in allowed | {''} or d['estado'] not in {'desconocido', 'confirmado', 'conflicto'}:
                return False
            if d['estado'] == 'confirmado' and (not d['valor'] or d['turno'] == 0):
                return False
            if d['estado'] == 'desconocido' and d['valor']:
                return False
            if d['origen'] not in {'ausente', 'explicito', 'observacion'}:
                return False
            if d['estado'] == 'confirmado' and d['origen'] == 'ausente':
                return False
        # Solo los contextos V2 incorporan estas dimensiones. V1 no cambia.
        for field, allowed in {'dni_previo': {'si', 'no'},
                               'funcion_documento': {'titular', 'apoyo'}}.items():
            if field not in c:
                continue
            d = c[field]
            if (set(d) != {'valor', 'estado', 'turno', 'revision', 'origen'}
                    or type(d['turno']) is not int or type(d['revision']) is not int
                    or d['revision'] != c['revision'] or not 0 <= d['turno'] <= c['turno']
                    or d['valor'] not in allowed | {''}
                    or d['estado'] not in {'desconocido', 'confirmado', 'conflicto'}
                    or d['origen'] not in {'ausente', 'explicito', 'observacion'}
                    or (d['estado'] == 'confirmado' and
                        (not d['valor'] or not d['turno'] or d['origen'] == 'ausente'))
                    or (d['estado'] == 'desconocido' and d['valor'])):
                return False
            reason = 'documento' if field == 'funcion_documento' else field
            if d['estado'] == 'conflicto' and reason not in c['pendientes']:
                return False
        if ('dni_previo' in c and c['dni_previo']['estado'] == 'confirmado'
                and c['operacion']['estado'] == 'confirmado'
                and ((c['operacion']['valor'] == 'primera_vez' and c['dni_previo']['valor'] == 'si')
                     or (c['operacion']['valor'] in {'renovacion', 'duplicado'}
                         and c['dni_previo']['valor'] == 'no'))
                and 'dni_previo' not in c['pendientes']):
            return False
        if c['operacion']['valor'] in c['rechazadas']:
            return False
        if c['propuesta_operacion'] in c['rechazadas']:
            return False
        if (c['operacion']['estado'] == 'confirmado'
                and c['propuesta_operacion'] not in {'', c['operacion']['valor']}):
            return False
        if c['pendientes'] and c['retomar']:
            return False
        if c['edad']['estado'] == 'conflicto' and 'edad' not in c['pendientes']:
            return False
        if c['titular']['estado'] == 'conflicto' and 'titular' not in c['pendientes']:
            return False
        if c['operacion']['estado'] == 'conflicto' and not ({'operacion', 'dni_previo'} & c['pendientes'].keys()):
            return False
        return True
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def _conocido(c, field):
    return c[field]['estado'] == 'confirmado'


def tramite_candidato(c: ContextoCanonico) -> str:
    op = c['propuesta_operacion'] or c['operacion']['valor']
    if op == 'duplicado':
        return 'dni_duplicado'
    if op:
        group = c['edad']['valor'] if _conocido(c, 'edad') else 'sin_edad'
        return f'dni_{group}_{op}'
    return 'dni_consulta_estado' if c['tema'] == 'seguimiento' and c['ambito'] == 'dni' else 'dni_por_aclarar'


def ruta_documental(c: dict | None) -> str:
    """Solo un contexto validado y sin dudas autoriza una ruta del corpus."""
    if not c or not validar_contexto(c) or c['ambito'] != 'dni' or c['pendientes']:
        return ''
    if c['tema'] == 'seguimiento':
        return 'dni_consulta_estado'
    if not _conocido(c, 'operacion') or c['operacion']['valor'] in c['rechazadas']:
        return ''
    if c['operacion']['valor'] in {'primera_vez', 'renovacion'} and not _conocido(c, 'edad'):
        return ''
    candidate = tramite_candidato(c)
    return candidate if candidate in DOCUMENTADOS else ''


def transicionar(anterior: ContextoCanonico | None, e: EvidenciaTurno) -> ContextoCanonico:
    """No consulta campos legados; rechazos y procedencia sobreviven a los turnos."""
    if anterior is not None and not validar_contexto(anterior):
        raise ValueError('Contexto canónico inválido')
    c = deepcopy(anterior) if anterior else contexto_inicial()
    c['turno'] += 1
    c['retomar'] = ''
    had_pending = bool(c['pendientes'])
    old_topic = c['consulta_pendiente']
    old_op = c['operacion']['valor']
    old_group = c['edad']['valor']
    scope = c['ambito'] == 'dni'
    outside = not e.mixto and (e.otro_tramite or (e.mencion_otro and e.tema == 'seguimiento' and not e.dni)
        or (not scope and (e.otro_solo or (e.otro_necesitado and not e.finalidad_dni and not e.apoyo)
            or (e.mencion_otro and not e.dni and not e.apoyo))))
    if outside or e.abandonar:
        c = contexto_inicial(c['revision'] + 1, c['turno'])
        if outside:
            c['ambito'] = 'fuera_alcance'
            return c
        scope = False
        had_pending = False
        old_topic = ''
    if e.dni:
        c['ambito'] = 'dni'
    elif c['ambito'] == 'fuera_alcance':
        c['ambito'] = 'desconocido'

    generic = e.cambio and e.tema == 'seguimiento' and not e.dudas and c['ambito'] == 'dni'
    selected = bool(e.titular) and 'titular' not in e.dudas
    # Completar un titular desconocido no es sustituir uno ya confirmado.
    replaced = selected and _conocido(c, 'titular') and (
        e.otro_titular or e.titular != c['titular']['valor']
        or (e.solicitud and e.edad and old_group and e.edad != old_group and 'edad' not in c['pendientes']))
    plural = 'titular' in e.dudas
    if generic or replaced or plural:
        last = c['ultima_ruta']
        c = contexto_inicial(c['revision'] + 1, c['turno'])
        c['ambito'] = 'dni' if scope or e.dni else 'desconocido'
        c['ultima_ruta'] = last
        if replaced and had_pending and not e.cambio:
            c['consulta_pendiente'] = old_topic
        if plural:
            c['pendientes']['titular'] = 'contradiccion'
            c['titular'] = dato(revision=c['revision'], estado='conflicto')
        had_pending = had_pending and not (generic or (e.cambio and replaced))
    c['tema'] = e.tema

    def confirm(field, value):
        c[field] = dato(value, c['turno'], c['revision'],
                       origen='observacion' if field == 'operacion' and e.observacion else None)

    def doubt(field, reason):
        c[field]['estado'] = 'conflicto'
        c['pendientes'][reason] = 'contradiccion'

    # Rechazar es un evento persistente, independiente de las demás dudas.
    c['rechazadas'] = sorted(set(c['rechazadas']) | (set(e.rechazadas) & OPERACIONES))
    if c['operacion']['valor'] in c['rechazadas']:
        c['operacion'] = dato(revision=c['revision'])
    if c['propuesta_operacion'] in c['rechazadas']:
        c['propuesta_operacion'] = ''

    if selected and not generic:
        confirm('titular', e.titular)
        c['pendientes'].pop('titular', None)
    if 'edad' in e.dudas:
        doubt('edad', 'edad')
    elif e.edad and not plural and (not ('titular' in c['pendientes']) or selected):
        if (_conocido(c, 'edad') and e.edad != c['edad']['valor']
                and not e.solicitud and not e.rectificacion and 'edad' not in c['pendientes']):
            doubt('edad', 'edad')
        else:
            confirm('edad', e.edad)
            c['pendientes'].pop('edad', None)

    if 'documento' in e.dudas:
        c['pendientes']['documento'] = 'contradiccion'
    elif 'documento' in c['pendientes']:
        complete_request = selected and bool(e.operacion) and e.solicitud
        if e.funcion_documento or complete_request:
            c['pendientes'].pop('documento', None)
            if e.funcion_documento == 'titular' and not selected:
                c['pendientes']['titular'] = 'contradiccion'
                c['titular'] = dato(revision=c['revision'], estado='conflicto')
                c['edad'] = dato(revision=c['revision'])

    if e.mixto:
        c['pendientes']['contradiccion'] = 'contradiccion'
    elif e.dni and e.operacion and not e.dudas:
        c['pendientes'].pop('contradiccion', None)
    if 'operacion' in e.dudas:
        doubt('operacion', 'operacion')
        c['propuesta_operacion'] = ''
    elif e.operacion and c['ambito'] == 'dni' and not generic:
        # Una observación no rehabilita una operación rechazada.
        permitted = e.operacion not in c['rechazadas'] or not e.observacion
        incompatible = (old_op and e.operacion != old_op and e.observacion
            and not ({'dni_previo', 'operacion'} & c['pendientes'].keys())
            and not e.rectificacion and old_op not in e.rechazadas and not replaced)
        if not permitted:
            # El hecho puede ser contradictorio, pero nunca se convierte en
            # aceptación de la operación rechazada ni en candidato autorizado.
            doubt('operacion', 'dni_previo' if incompatible else 'operacion')
            c['propuesta_operacion'] = ''
        elif incompatible:
            doubt('operacion', 'dni_previo')
            c['propuesta_operacion'] = e.operacion
        elif permitted:
            if not e.observacion:
                c['rechazadas'] = [op for op in c['rechazadas'] if op != e.operacion]
            confirm('operacion', e.operacion)
            c['propuesta_operacion'] = e.operacion
            c['pendientes'].pop('operacion', None)
            c['pendientes'].pop('dni_previo', None)

    if e.mencion_otro and not e.dni and not e.apoyo:
        c['pendientes']['tramite'] = 'faltante'
    elif e.dni:
        c['pendientes'].pop('tramite', None)
    if c['ambito'] != 'dni':
        c['pendientes']['tramite'] = 'faltante'
    elif not generic:
        if not _conocido(c, 'operacion') and e.tema != 'seguimiento':
            c['pendientes'].setdefault('operacion', 'faltante')
        if (_conocido(c, 'operacion') and c['operacion']['valor'] in {'primera_vez', 'renovacion'}
                and not _conocido(c, 'edad')):
            c['pendientes'].setdefault('edad', 'faltante')
    if c['pendientes']:
        if e.pregunta_tema:
            c['consulta_pendiente'] = e.tema
        else:
            c['consulta_pendiente'] = c['consulta_pendiente'] or old_topic or (anterior['tema'] if anterior and not e.abandonar and anterior['tema'] != 'otra' else 'otra')
    else:
        if had_pending and old_topic and not e.pregunta_tema and not e.cambio:
            c['tema'] = old_topic
            c['retomar'] = old_topic
        c['consulta_pendiente'] = ''
        if c['ambito'] == 'dni':
            c['ultima_ruta'] = tramite_candidato(c)
    if not validar_contexto(c):
        raise ValueError('Transición inconsistente')
    return c


def transicionar_v2(
    anterior: ContextoCanonico, interpretacion: 'InterpretacionTurno',
) -> ContextoCanonico:
    """Política V2 optativa; no es llamada por clasificación/grafo V1.

    Revalidación defensiva también para llamadas directas. Las referencias se
    comprueban, pero nunca se reescriben como evidencia del turno actual.
    """
    from app.graph.interpretation_contract import InterpretacionTurno

    if not validar_contexto(anterior):
        raise ValueError('Contexto canónico inválido')
    interpretacion = InterpretacionTurno.model_validate(interpretacion.model_dump())
    c = deepcopy(anterior)
    c['turno'] += 1
    c['retomar'] = ''
    before_topic = c['consulta_pendiente']
    had_pending = bool(c['pendientes'])
    reasons = {'ambito': 'tramite', 'tema': 'tramite', 'referencia': 'titular',
               'referencia_titular': 'titular', 'funcion_documento': 'documento'}
    fields = {'titular', 'edad', 'operacion', 'dni_previo', 'funcion_documento'}
    for field in ('dni_previo', 'funcion_documento'):
        c.setdefault(field, dato(revision=c['revision']))
    blocks = {reasons.get(x, x): 'faltante' for x in interpretacion.faltantes}
    blocks.update({reasons.get(x, x): 'contradiccion' for x in interpretacion.contradicciones})
    if not interpretacion.evidencias:
        blocks['tramite'] = 'contradiccion'
    positive = {}
    negative = {}
    references = []
    for e in interpretacion.evidencias:
        reason = reasons.get(e.dimension, e.dimension)
        if e.sujeto != 'objetivo':
            blocks['titular'] = 'contradiccion'
            continue
        if e.origen == 'referencia_contextual':
            references.append(e)
            continue
        if e.valor in {'desconocido', 'ambigua', 'varios'}:
            blocks[reason] = 'contradiccion'
            continue
        target = negative if e.acto == 'negacion' else positive
        target.setdefault(e.dimension, []).append(e)
    # Una contradicción local nunca se resuelve por el orden de las evidencias.
    for dim, items in positive.items():
        if (len({e.valor for e in items}) > 1
                or {e.valor for e in items} & {e.valor for e in negative.get(dim, [])}):
            blocks[reasons.get(dim, dim)] = 'contradiccion'
    selected = {dim: max(items, key=lambda e: e.acto in {'aclaracion', 'solicitud_afirmativa'})
                for dim, items in positive.items() if reasons.get(dim, dim) not in blocks}
    holder = selected.get('titular')
    ref = selected.get('referencia_titular')
    changed = (ref is not None and ref.valor == 'otro') or (
        holder is not None and c['titular']['estado'] == 'confirmado'
        and holder.valor != c['titular']['valor'])
    if changed or 'titular' in blocks:
        # Incluso la misma categoría puede representar a otra persona.
        revision, turno = c['revision'] + 1, c['turno']
        c = contexto_inicial(revision, turno)
        c['ambito'] = anterior['ambito']
        for field in ('dni_previo', 'funcion_documento'):
            c[field] = dato(revision=revision)
        if (not holder or holder.acto not in {'solicitud_afirmativa', 'aclaracion'}
                or 'titular' in blocks):
            blocks['titular'] = 'contradiccion'
            c['rechazadas'] = list(anterior['rechazadas'])
    if (ref and ref.valor == 'actual' and c['titular']['estado'] != 'confirmado'):
        blocks['titular'] = 'contradiccion'
    for e in references:
        dim = e.dimension
        compatible = (not changed and 'titular' not in blocks
                      and c['titular']['estado'] == 'confirmado')
        if dim in fields:
            compatible = (compatible and c[dim]['estado'] == 'confirmado'
                          and c[dim]['valor'] == e.valor)
        elif dim == 'ambito':
            compatible = compatible and c['ambito'] == e.valor
        elif dim == 'referencia_titular':
            compatible = compatible and e.valor == 'actual'
        else:
            compatible = False  # Tema heredado o referencia no representable.
        if dim in selected and selected[dim].valor != e.valor:
            compatible = False
        if not compatible or e.acto == 'negacion':
            blocks[reasons.get(dim, dim)] = 'contradiccion'
    full_request = all(dim in selected and selected[dim].acto in
                       {'solicitud_afirmativa', 'aclaracion'}
                       for dim in ('titular', 'edad', 'operacion')) and 'ambito' in selected
    # Un fallo genérico no se cierra por una palabra temática o una referencia.
    if full_request and not blocks:
        c['pendientes'].pop('tramite', None)
        c['pendientes'].pop('contradiccion', None)
    scope = selected.get('ambito')
    if scope and scope.valor == 'fuera_alcance':
        c = contexto_inicial(c['revision'] + 1, c['turno'])
        c['ambito'] = 'fuera_alcance'
    elif scope and scope.valor == 'dni':
        c['ambito'] = 'dni'
    for dim, items in negative.items():
        reason = reasons.get(dim, dim)
        if dim == 'operacion':
            c['rechazadas'] = sorted(set(c['rechazadas']) | {e.valor for e in items})
            if c['operacion']['valor'] in c['rechazadas']:
                c['operacion'] = dato(revision=c['revision'])
                c['propuesta_operacion'] = ''
                c['pendientes']['operacion'] = 'faltante'
        else:
            # No inferir adulto desde «no es menor», ni apoyo desde «no es titular».
            blocks[reason] = 'contradiccion'
    for dim in fields:
        e = selected.get(dim)
        reason = reasons.get(dim, dim)
        if not e or reason in blocks or 'titular' in blocks:
            continue
        old = c.get(dim, dato(revision=c['revision']))
        explicit = e.acto in {'solicitud_afirmativa', 'aclaracion'}
        if dim == 'operacion' and not explicit:
            if old['estado'] != 'confirmado' or old['valor'] != e.valor or e.valor in c['rechazadas']:
                blocks['operacion'] = 'contradiccion'
            continue
        if reason in c['pendientes'] and not explicit and c['pendientes'][reason] == 'contradiccion':
            continue
        if old['estado'] == 'confirmado' and old['valor'] != e.valor and not explicit:
            blocks[reason] = 'contradiccion'
            continue
        c[dim] = dato(e.valor, c['turno'], c['revision'],
                      origen='explicito' if explicit else 'observacion')
        c['pendientes'].pop(reason, None)
        if dim == 'operacion':
            c['rechazadas'] = [op for op in c['rechazadas'] if op != e.valor]
            c['propuesta_operacion'] = e.valor
    topic = selected.get('tema')
    if topic:
        c['tema'] = topic.valor
    if (c['tema'] == 'seguimiento' and c['operacion']['estado'] != 'confirmado'
            and (not topic or topic.acto not in {'solicitud_afirmativa', 'aclaracion'})):
        blocks['tramite'] = 'faltante'
    op = c['operacion']['valor']
    prior = c.get('dni_previo', dato())
    if (prior['estado'] == 'confirmado' and
            ((op == 'primera_vez' and prior['valor'] == 'si') or
             (op in {'renovacion', 'duplicado'} and prior['valor'] == 'no'))):
        blocks['dni_previo'] = 'contradiccion'
    elif ('dni_previo' in c['pendientes'] and
          any(dim in selected and selected[dim].acto in {'aclaracion', 'solicitud_afirmativa'}
              for dim in ('dni_previo', 'operacion')) and prior['estado'] == 'confirmado'):
        c['pendientes'].pop('dni_previo', None)
    if c['ambito'] != 'dni':
        blocks.setdefault('tramite', 'faltante')
    if c['tema'] != 'seguimiento' and c['ambito'] == 'dni':
        for dim in ('titular', 'edad', 'operacion'):
            if c[dim]['estado'] != 'confirmado':
                c['pendientes'].setdefault(dim, 'faltante')
    c['pendientes'].update(blocks)
    if c['pendientes']:
        c['consulta_pendiente'] = (topic.valor if topic else before_topic or anterior['tema'])
    else:
        c['consulta_pendiente'] = ''
        if had_pending and before_topic and not topic and not changed:
            c['tema'] = before_topic
            c['retomar'] = before_topic
        c['ultima_ruta'] = tramite_candidato(c)
    if not validar_contexto(c):
        raise ValueError('Transición V2 inconsistente')
    return c
