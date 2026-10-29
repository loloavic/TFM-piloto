"""Condiciones categóricas y contrato documental de adultos; sin datos identificativos."""
import re

VALORES = {
    'modificacion': {'ninguna', 'datos', 'estado_civil', 'domicilio', 'imagen_firma'},
    'transicion': {'matrimonio', 'divorcio', 'viudez'},
    'matrimonio': {'peru', 'extranjero'},
    'defuncion': {'peru', 'italia', 'otro'},
    'italiano': {'si', 'no'}, 'apellido': {'si', 'no'},
    'vigencia': {'vencido', 'vigente', 'hasta_60', 'mas_60'},
}
REGLAS_COMUNES = {'plazo', 'seguimiento', 'advertencias'}

ADULT_FILES = {
    'dni_adulto_renovacion': 'dni_mayor_renovacion.txt',
    'dni_adulto_rectificacion': 'dni_mayor_rectificacion.txt',
}


def extraer(text):
    """Solo categorías; las negaciones se procesan antes que las afirmaciones."""
    facts = {}
    text = re.sub(r'\bno (?:me case|nos casamos|me divorcie|soy viud[oa])[^,;.!?]*', ' ', text)
    clean = re.sub(r'\bno (?:quiero|necesito|deseo) (?:rectificar|corregir|cambiar|actualizar)[^.;?!]*', ' ', text)
    if re.search(r'\b(?:rectificar|rectificacion|corregir|correccion|cambiar|cambio|actualizar|actualizacion)\b', clean):
        if re.search(r'estado civil|casad|casarme|matrimonio|divorci|viud', clean):
            facts['modificacion'] = 'estado_civil'
        elif re.search(r'nombres?|apellidos?|nacimiento|datos (?:personales|de (?:mis |los )?padres)', clean):
            facts['modificacion'] = 'datos'
        elif re.search(r'direccion|domicilio', clean):
            facts['modificacion'] = 'domicilio'
        elif re.search(r'imagen|firma', clean):
            facts['modificacion'] = 'imagen_firma'
    if re.fullmatch(r'(?:a )?(casad[oa]|divorciad[oa]|viud[oa])[.!]?', clean):
        facts.update(modificacion='estado_civil', transicion=('matrimonio' if 'casad' in clean else 'divorcio' if 'divorciad' in clean else 'viudez'))
    # Aclaraciones sobre circunstancias de una modificación ya solicitada.
    if re.search(r'\b(?:me case|nos casamos|de solter[oa] a casad[oa])\b', clean):
        facts.update(modificacion='estado_civil', transicion='matrimonio')
    if re.search(r'\b(?:me divorcie|de casad[oa] a divorciad[oa])\b', clean):
        facts.update(modificacion='estado_civil', transicion='divorcio')
    if re.search(r'\b(?:soy viud[oa]|de casad[oa] a viud[oa]|mi (?:conyuge|esposo|esposa) (?:murio|fallecio))\b', clean):
        facts.update(modificacion='estado_civil', transicion='viudez')
    if re.search(r'\b(?:matrimonio|me case|nos casamos)\b.*\b(?:en (?:el )?peru)\b', clean):
        facts['matrimonio'] = 'peru'
    elif re.search(r'\b(?:matrimonio|me case|nos casamos)\b.*(?:fuera (?:de|del) peru|en (?:italia|el extranjero))', clean):
        facts['matrimonio'] = 'extranjero'
    death = re.search(r'(?:defuncion|fallecio|murio)\b[^.;?!]*?\ben (?:el )?(peru|italia|otro pais)\b', clean)
    if death:
        facts['defuncion'] = {'peru':'peru','italia':'italia','otro pais':'otro'}[death[1]]
    nationality = nacionalidad(text)
    if nationality:
        facts['italiano'] = nationality
    if re.search(r'\brecuperar (?:mi |el )?apellido materno\b', text):
        facts['apellido'] = 'no' if re.search(r'\bno (?:quiero |deseo |necesito )?recuperar\b', text) else 'si'
    if re.search(r'\b(?:sin (?:cambios|modificaciones)|solo (?:quiero )?renovar|no (?:quiero|necesito) (?:rectificar|corregir|cambiar|actualizar)(?!\s+(?:mi|el)\s+apellido\b))\b', text):
        facts['modificacion'] = 'ninguna'
    validity = extraer_vigencia(text)
    if validity:
        facts['vigencia'] = validity
    if (facts.get('modificacion') == 'estado_civil'
            and re.search(r'\b(?:nombres?|datos personales|datos de nacimiento)\b', clean)):
        facts['modificacion'] = 'conflicto'
    if (re.search(r'\b(?:matrimonio|me case|nos casamos)\b.*\ben (?:el )?peru\b', clean)
            and re.search(r'\b(?:matrimonio|me case|nos casamos)\b.*(?:fuera (?:de|del) peru|en (?:italia|el extranjero))', clean)):
        facts['matrimonio'] = 'conflicto'
    return tuple(sorted(facts.items()))


def actualizar(c, evidence):
    """Escritor subordinado a la transición canónica y su revisión del titular."""
    from app.graph.context_policy import dato
    conditions = c.setdefault('condiciones_adulto', {})
    if evidence.cambio and evidence.operacion and not evidence.observacion:
        validity = conditions.get('vigencia')
        conditions.clear()
        # Cambiar de operación no cambia la vigencia del mismo titular.
        # Un cambio de titular ya invalida el contexto/revisión en la política.
        if validity and validity.get('revision') == c['revision']:
            conditions['vigencia'] = validity
    incoming = dict(evidence.condiciones_adulto)
    if evidence.lugar_confirmado:
        if 'adulto_matrimonio' in c['pendientes']:
            incoming.setdefault('matrimonio', 'peru' if evidence.lugar_confirmado == 'peru' else 'extranjero')
        elif 'adulto_defuncion' in c['pendientes']:
            incoming.setdefault('defuncion', evidence.lugar_confirmado)
    if (evidence.respuesta_apellido and valor(c, 'modificacion') == 'estado_civil'
            and valor(c, 'transicion') in {'divorcio', 'viudez'}
            and ('adulto_apellido' in c['pendientes'] or 'apellido' in conditions)):
        incoming['apellido'] = evidence.respuesta_apellido
    if (evidence.respuesta_nacionalidad
            and valor(c, 'modificacion') == 'estado_civil'
            and valor(c, 'transicion') == 'viudez'
            and valor(c, 'defuncion') == 'italia'
            and ('adulto_italiano' in c['pendientes'] or 'italiano' in conditions)):
        incoming.setdefault('italiano', evidence.respuesta_nacionalidad)
    # Las respuestas breves solo completan la dimensión preguntada.
    if evidence.respuesta_binaria:
        for key in ('italiano', 'apellido'):
            if 'adulto_' + key in c['pendientes']:
                incoming.setdefault(key, evidence.respuesta_binaria)
                break
    for key in incoming:
        if key not in VALORES or incoming[key] not in VALORES[key] | {'conflicto'}:
            raise ValueError('Condición de adulto no válida')
    # Cambiar de modificación o transición invalida sus datos dependientes.
    if ('modificacion' in incoming and incoming['modificacion'] != valor(c, 'modificacion')):
        for key in ('transicion', 'matrimonio', 'defuncion', 'italiano', 'apellido'):
            conditions.pop(key, None)
    if 'transicion' in incoming and incoming['transicion'] != valor(c, 'transicion'):
        for key in ('matrimonio', 'defuncion', 'italiano', 'apellido'):
            conditions.pop(key, None)
    for key, value in incoming.items():
        conditions[key] = dato(value if value != 'conflicto' else '', c['turno'], c['revision'],
                               estado='conflicto' if value == 'conflicto' else 'confirmado', origen='explicito')
    op = c['operacion']['valor']
    # La ficha deriva rectificación de DNI vencido también a renovación.
    # Se mantiene la operación solicitada; el plan autoriza ambas fuentes.
    for key in list(c['pendientes']):
        if key.startswith('adulto_'):
            c['pendientes'].pop(key)
    for key, d in conditions.items():
        if d['estado'] == 'conflicto':
            c['pendientes']['adulto_' + key] = 'contradiccion'
    if c['edad']['estado'] != 'confirmado' or c['edad']['valor'] != 'adulto' or op not in {'renovacion','rectificacion'}:
        return
    if op == 'rectificacion' and valor(c, 'vigencia') in {'vencido', 'hasta_60'} and 'renovacion' in c['rechazadas']:
        c['pendientes']['adulto_derivacion'] = 'contradiccion'
    if (op == 'renovacion' and valor(c, 'modificacion') in {'datos', 'imagen_firma'}
            and valor(c, 'vigencia') in {'', 'vigente'}):
        c['pendientes']['adulto_vigencia'] = 'faltante'
    if op == 'renovacion' and valor(c, 'modificacion') == 'estado_civil':
        return
    topic = c['consulta_pendiente'] if c['consulta_pendiente'] and not evidence.pregunta_tema else c['tema']
    if topic not in {'otra', 'requisitos'}:
        return
    mod = valor(c, 'modificacion')
    if op == 'rectificacion' and not mod:
        c['pendientes'].setdefault('adulto_modificacion', 'faltante')
    if mod == 'estado_civil':
        transition = valor(c, 'transicion')
        required = ['transicion'] if not transition else []
        if transition == 'matrimonio' and not valor(c, 'matrimonio'):
            required.append('matrimonio')
        if transition in {'divorcio', 'viudez'} and not valor(c, 'apellido'):
            required.append('apellido')
        if transition == 'viudez' and not valor(c, 'defuncion'):
            required.append('defuncion')
        if transition == 'viudez' and valor(c, 'defuncion') == 'italia' and not valor(c, 'italiano'):
            required.append('italiano')
        for key in required:
            c['pendientes'].setdefault('adulto_' + key, 'faltante')


def valor(c, key):
    d = c.get('condiciones_adulto', {}).get(key, {})
    return d.get('valor', '') if d.get('estado') == 'confirmado' else ''


def validar(c):
    for key, d in c.get('condiciones_adulto', {}).items():
        if key not in VALORES:
            return False
        conflict = d.get('estado') == 'conflicto'
        if conflict:
            if d.get('valor') or c['pendientes'].get('adulto_' + key) != 'contradiccion':
                return False
        elif d.get('valor') not in VALORES[key]:
            return False
        if (d.get('estado') not in {'confirmado', 'conflicto'} or d.get('origen') != 'explicito'
                or d.get('revision') != c['revision'] or not 0 < d.get('turno', -1) <= c['turno']):
            return False
    return True


def plan(c):
    """Archivos exactos. Nunca mezcla menores; solo combina la derivación documentada."""
    op = c['operacion']['valor']
    mod = valor(c, 'modificacion')
    if op == 'renovacion' and valor(c, 'vigencia') == 'mas_60':
        return {'dni_mayor_renovacion.txt': {'general'}}
    if c['tema'] in REGLAS_COMUNES:
        # Alcance común confirmado; no autoriza requisitos específicos ni combinaciones.
        if op == 'renovacion' and mod in {'datos','imagen_firma'} and valor(c,'vigencia') in {'vencido', 'hasta_60'}:
            return {file: {c['tema']} for file in ('dni_mayor_renovacion.txt','dni_mayor_rectificacion.txt')}
        if op == 'rectificacion' and mod != 'estado_civil' and valor(c,'vigencia') in {'vencido', 'hasta_60'}:
            return {file: {c['tema']} for file in ('dni_mayor_renovacion.txt','dni_mayor_rectificacion.txt')}
        file = 'dni_mayor_estado_civil.txt' if mod == 'estado_civil' and op == 'rectificacion' else ADULT_FILES.get('dni_adulto_' + op)
        return {file: {c['tema']}} if file else {}
    if mod == 'estado_civil':
        # La ficha no autoriza sumar estado civil a una renovación.
        if op == 'renovacion':
            return {}
        rules = {'general'}
        transition = valor(c, 'transicion')
        if c['tema'] in {'otra', 'requisitos'}:
            if transition == 'matrimonio':
                rules.add('matrimonio_' + valor(c, 'matrimonio'))
            elif transition == 'divorcio':
                rules.add('divorcio')
            elif transition == 'viudez':
                rules.add('viudez_' + valor(c, 'defuncion'))
                if valor(c, 'defuncion') == 'italia' and valor(c, 'italiano') == 'si':
                    rules.add('italiano')
            if transition in {'divorcio', 'viudez'} and valor(c, 'apellido') == 'si':
                rules.add('apellido')
        return {'dni_mayor_estado_civil.txt': rules}
    if op == 'renovacion':
        if mod in {'datos', 'imagen_firma'}:
            if valor(c, 'vigencia') not in {'vencido', 'hasta_60'}:
                return {}
            return {'dni_mayor_renovacion.txt': {'general', 'no_acumulacion'}, 'dni_mayor_rectificacion.txt': {'general', mod}}
        return {'dni_mayor_renovacion.txt': {'general'}}
    result = {'dni_mayor_rectificacion.txt': {'general', mod} - {''}}
    if valor(c, 'vigencia') in {'vencido', 'hasta_60'}:
        result['dni_mayor_renovacion.txt'] = {'general', 'no_acumulacion'}
    return result


PREGUNTAS = {
    'adulto_vigencia': '¿El DNI está vencido, vence dentro de 60 días o menos, o le quedan más de 60 días? No indique la fecha exacta.',
    'adulto_derivacion': 'La vigencia indicada permite renovación, que ha rechazado. Aclare si solicita también renovación o desea consultar al Consulado antes de continuar.',
    'adulto_modificacion': '¿Desea rectificar datos personales, dirección, imagen o firma, o estado civil?',
    'adulto_transicion': '¿El cambio es a casado, divorciado o viudo?',
    'adulto_matrimonio': '¿El matrimonio se celebró en Perú o fuera de Perú?',
    'adulto_defuncion': '¿La defunción ocurrió en Perú, Italia u otro país?',
    'adulto_italiano': '¿El cónyuge fallecido era italiano? Indique solo sí o no, sin datos identificativos.',
    'adulto_apellido': '¿Desea recuperar el apellido materno? No indique su apellido.',
}


# Las referencias al cónyuge y las respuestas elípticas tienen ámbitos distintos.
_NATIONAL_CLAUSE = r'(no\s+)?(?:era|es)\s+(?:ciudadan[oa]\s+|de nacionalidad\s+)?italian[oa]\b'


def nacionalidad(text):
    """Solo un cónyuge explícito; otra persona no acredita esta condición."""
    subject = (r'\b(?:mi\s+)?(?:conyuge|esposo|esposa)\s+'
               r'(?:(?:fallecio|murio)\s+en\s+(?:italia|peru|otro pais)\s+y\s+)?')
    values = {'no' if m[1] else 'si' for m in re.finditer(subject + _NATIONAL_CLAUSE, text)}
    return 'conflicto' if len(values) > 1 else next(iter(values), '')


def respuesta_nacionalidad(text):
    """Fragmento solo aplicable a una condición de cónyuge ya contextualizada."""
    text = re.sub(r'^(?:me equivoque|en realidad)[, ]+', '', text)
    if re.fullmatch(r'no[, ]+(?:era|es) (?:ciudadan[oa] )?peruan[oa][.!]?', text):
        return 'no'  # El no explícito responde a la pregunta; no excluye por nacionalidad.
    match = re.fullmatch(r'(?:(si[, ]+|no,\s*))?' + _NATIONAL_CLAUSE + r'[.!]?', text)
    if not match:
        return ''
    prefix, negative = (match[1] or '').strip(' ,'), match[2]
    if prefix == 'si' and negative:
        return 'conflicto'
    if prefix == 'no' and not negative:
        return 'conflicto'  # «no, era italiano» no confirma un valor inequívoco.
    return 'no' if negative else 'si'


def respuesta_apellido(text):
    """Decisión sobre recuperar apellido, nunca el apellido ni una identidad."""
    negative = bool(re.search(
        r'\bno (?:quiero|necesito|deseo) (?:cambiar|recuperar) (?:mi|el) apellido(?: materno)?\b|'
        r'\bno[, ]+(?:(?:ya )?(?:utilizo|uso|mantengo)|he mantenido(?: siempre)?) mi apellido materno\b', text))
    positive_text = re.sub(r'\bno (?:quiero|necesito|deseo) recuperar[^.;?!]*', ' ', text)
    positive = bool(re.search(r'\b(?:quiero|necesito|deseo) recuperar (?:mi|el) apellido materno\b', positive_text))
    return 'conflicto' if negative and positive else 'no' if negative else 'si' if positive else ''


def extraer_vigencia(text):
    """Solo categorías; no conservar números, fechas ni asumir meses de 30 días."""
    no_expired = re.search(r'\bno (?:esta |ha )?(?:vencido|caducado|expirado)\b', text)
    positive = re.sub(r'\bno (?:esta |ha )?(?:vencido|caducado|expirado)\b', ' ', text)
    values = set()
    if re.search(r'\b(?:vencido|caducado|expirado)\b', positive):
        values.add('vencido')
    if re.search(r'\b(?:mas de 60 dias|mas de sesenta dias)\b', text):
        values.add('mas_60')
    if re.search(r'\b(?:60 dias o menos|sesenta dias o menos|menos de 60 dias)\b', text):
        values.add('hasta_60')
    quantity = re.search(r'\b(?:vence (?:en|dentro de)|vencera (?:en|dentro de)|faltan|(?:le )?quedan|tiene)\s+'
                         r'(\d{1,4}|un|uno|dos|tres|cuatro|cinco|seis)\s+(dias?|meses?|semanas?)\b', text)
    if quantity and quantity[0].startswith('tiene') and not re.match(r'\s+de vigencia', text[quantity.end():]):
        quantity = None
    if quantity and quantity[0].startswith('faltan') and not re.match(
            r'\s+para (?:su |el )?(?:vencimiento|vencer)', text[quantity.end():]):
        quantity = None
    if quantity:
        words = {'un':1,'uno':1,'dos':2,'tres':3,'cuatro':4,'cinco':5,'seis':6}
        n = int(quantity[1]) if quantity[1].isdigit() else words[quantity[1]]
        unit = quantity[2]
        if unit.startswith('mes'):
            category = 'mas_60' if n >= 3 else 'hasta_60' if n <= 1 else 'vigente'
        else:
            days = n * 7 if unit.startswith('semana') else n
            category = 'hasta_60' if days <= 60 else 'mas_60'
        values.add(category)
    specific = values - {'vigente'}
    if len(specific) > 1:
        return 'conflicto'
    if values:
        return next(iter(specific or values))
    if no_expired or re.search(r'\bdni\b[^.;?!]*\bvigente\b', text):
        return 'vigente'
    return ''
