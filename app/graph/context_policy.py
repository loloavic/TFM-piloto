"""Único escritor del contexto: transición pura, sin texto, proveedor ni historial."""
from copy import deepcopy

from app.graph.state import ContextoCanonico, DatoContextual, EvidenciaTurno
from app.graph.adult_context import ADULT_FILES, PREGUNTAS, actualizar, validar as validar_adulto

CAMBIO_AZUL = 'amarillo_a_azul'
OPERACIONES = {'primera_vez', 'renovacion', 'duplicado', 'rectificacion', CAMBIO_AZUL}
DOCUMENTOS_POR_INTENCION = {
    'dni_menor_primera_vez': 'dni_menor_primera_vez.txt',
    'dni_menor_renovacion': 'dni_menor_renovacion.txt',
    'dni_consulta_estado': 'dni_consulta_estado.txt',
    'dni_amarillo_a_azul_primera_vez': 'dni_amarillo_a_azul_primera_vez.txt',
}
DOCUMENTOS_POR_INTENCION.update(ADULT_FILES)
DOCUMENTADOS = set(DOCUMENTOS_POR_INTENCION)
TEMAS = {'otra', 'coste', 'plazo', 'cita', 'requisitos', 'seguimiento', 'fotografias', 'advertencias'}
PRIORIDAD = ('titular', 'documento', 'tipo_dni', 'dni_previo', 'contradiccion', 'operacion', 'edad', 'tramite', *PREGUNTAS)
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
            'retomar': '', 'ultima_ruta': '', 'condiciones_adulto': {}, 'consulta_renovacion': []}


def validar_contexto(c: dict) -> bool:
    """Validación independiente de las etiquetas públicas y del extractor."""
    try:
        if c['ambito'] not in {'dni', 'desconocido', 'fuera_alcance'}:
            return False
        if c['turno'] < 0 or c['revision'] < 0 or c['tema'] not in TEMAS:
            return False
        purpose = c.get('consulta_renovacion', [])
        if (not isinstance(purpose, list) or any(not isinstance(x, str) for x in purpose)
                or set(purpose) - {'elegibilidad', 'coste', 'requisitos', 'fotografias', 'cita'}
                or (purpose and 'elegibilidad' not in purpose) or len(purpose) != len(set(purpose))):
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
        if c['operacion']['estado'] == 'conflicto' and not ({'operacion', 'dni_previo', 'tipo_dni'} & c['pendientes'].keys()):
            return False
        return validar_adulto(c)
    except (KeyError, TypeError, ValueError):
        return False


def _conocido(c, field):
    return c[field]['estado'] == 'confirmado'


def tramite_candidato(c: ContextoCanonico) -> str:
    if 'tipo_dni' in c['pendientes']:
        return 'dni_por_aclarar'
    op = c['propuesta_operacion'] or c['operacion']['valor']
    if op == CAMBIO_AZUL:
        return 'dni_amarillo_a_azul_primera_vez'
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
        candidate = tramite_candidato(c)
        if candidate in ADULT_FILES and _conocido(c,'operacion') and _conocido(c,'edad'):
            return candidate
        return 'dni_consulta_estado'
    if not _conocido(c, 'operacion') or c['operacion']['valor'] in c['rechazadas']:
        return ''
    if c['operacion']['valor'] in {'primera_vez', 'renovacion', 'rectificacion'} and not _conocido(c, 'edad'):
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
    if e.consulta_renovacion and c['ambito'] == 'dni':
        c['consulta_renovacion'] = list(e.consulta_renovacion)
    elif (e.tema != 'otra' or 'renovacion' in e.rechazadas
          or (e.operacion and e.operacion != 'renovacion' and e.solicitud)):
        c['consulta_renovacion'] = []
    else:
        c.setdefault('consulta_renovacion', [])

    def confirm(field, value):
        c[field] = dato(value, c['turno'], c['revision'],
                       origen='observacion' if field == 'operacion' and e.observacion else None)

    def doubt(field, reason):
        c[field]['estado'] = 'conflicto'
        c['pendientes'][reason] = 'contradiccion'

    # Completar la aclaración azul/amarillo usa la misma operación canónica.
    if ('tipo_dni' in c['pendientes'] and e.tiene_amarillo and CAMBIO_AZUL not in c['rechazadas']
            and not e.rechazadas and not e.dudas):
        from dataclasses import replace
        e = replace(e, operacion=CAMBIO_AZUL, observacion=False)
    if ('tipo_dni' in c['pendientes'] and e.operacion == 'primera_vez' and not e.nunca_tuvo_dni
            and not (e.cambio and e.solicitud)):
        # En una aclaración sobre azul, «primero» aún puede referirse al color.
        from dataclasses import replace
        e = replace(e, operacion='')
    if (not e.operacion and ((e.referencia_azul and c['operacion']['valor'] != CAMBIO_AZUL)
            or (e.tiene_amarillo and c['operacion']['valor'] in {'', 'primera_vez'}))):
        doubt('operacion', 'tipo_dni')
        c['propuesta_operacion'] = ''

    if (e.objetivo_independiente and e.operacion and old_op and e.operacion != old_op
            and 'adulto_derivacion' not in c['pendientes']):
        from dataclasses import replace
        e = replace(e, cambio=True)
        c['consulta_pendiente'] = e.tema
        c['retomar'] = ''

    if (old_op == 'rectificacion' and _conocido(c, 'edad') and c['edad']['valor'] == 'adulto'
            and e.operacion == 'renovacion' and e.observacion):
        # Tenencia/caducidad complementa la rectificación; no sustituye su operación.
        from dataclasses import replace
        e = replace(e, operacion='')
    if (e.operacion == 'rectificacion' and old_op == 'renovacion'
            and dict(e.condiciones_adulto).get('modificacion') and not e.cambio):
        from dataclasses import replace
        e = replace(e, operacion='')
    if ((e.edad == 'adulto' or (_conocido(c, 'edad') and c['edad']['valor'] == 'adulto'))
            and not c['operacion']['valor'] and not e.operacion
            and dict(e.condiciones_adulto).get('modificacion',
                c.get('condiciones_adulto', {}).get('modificacion', {}).get('valor')) not in {None, 'ninguna'}):
        from dataclasses import replace
        e = replace(e, operacion='rectificacion', observacion=True)
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
            if e.funcion_documento == 'titular' and not e.edad:
                # Resolver el rol no identifica cuál de los posibles hijos es
                # el titular. La edad anterior no sirve como confirmación.
                c['edad'] = dato(revision=c['revision'])
                c['pendientes']['edad'] = 'contradiccion'
                if not selected:
                    c['pendientes']['titular'] = 'contradiccion'
                    c['titular'] = dato(revision=c['revision'], estado='conflicto')

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
            c['pendientes'].pop('tipo_dni', None)

    if e.mencion_otro and not e.dni and not e.apoyo:
        c['pendientes']['tramite'] = 'faltante'
    elif e.dni:
        c['pendientes'].pop('tramite', None)
    if c['ambito'] != 'dni':
        c['pendientes']['tramite'] = 'faltante'
    elif not generic:
        if not _conocido(c, 'operacion') and e.tema != 'seguimiento':
            c['pendientes'].setdefault('operacion', 'faltante')
        if (_conocido(c, 'operacion') and c['operacion']['valor'] in {'primera_vez', 'renovacion', 'rectificacion'}
                and not _conocido(c, 'edad')):
            c['pendientes'].setdefault('edad', 'faltante')
    actualizar(c, e)
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
