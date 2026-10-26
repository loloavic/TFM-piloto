"""Condiciones categóricas y contrato documental de adultos; sin datos identificativos."""
import re

VALORES = {
    'modificacion': {'ninguna', 'datos', 'estado_civil', 'domicilio', 'imagen_firma'},
    'transicion': {'matrimonio', 'divorcio', 'viudez'},
    'matrimonio': {'peru', 'extranjero'},
    'defuncion': {'peru', 'italia', 'otro'},
    'italiano': {'si', 'no'}, 'apellido': {'si', 'no'},
    'vigencia': {'vencido', 'vigente'},
}
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
    death = re.search(r'(?:defuncion|fallecio|murio)\b.*\ben (?:el )?(peru|italia|otro pais)\b', clean)
    if death:
        facts['defuncion'] = {'peru':'peru','italia':'italia','otro pais':'otro'}[death[1]]
    if re.search(r'\b(?:conyuge|esposo|esposa)\b.*\b(?:era|es) italian[oa]\b', clean):
        facts['italiano'] = 'si'
    if re.search(r'\b(?:conyuge|esposo|esposa)\b.*\bno (?:era|es) italian[oa]\b', text):
        facts['italiano'] = 'no'
    if re.search(r'\brecuperar (?:mi |el )?apellido materno\b', text):
        facts['apellido'] = 'no' if re.search(r'\bno (?:quiero |deseo |necesito )?recuperar\b', text) else 'si'
    if re.search(r'\b(?:sin (?:cambios|modificaciones)|solo (?:quiero )?renovar|no (?:quiero|necesito) (?:rectificar|corregir|cambiar|actualizar))\b', text):
        facts['modificacion'] = 'ninguna'
    if re.search(r'\bdni\b.*\b(?:vencido|caducado|expirado)\b', text):
        facts['vigencia'] = 'vigente' if re.search(r'\bno (?:esta |ha )?(?:vencido|caducado|expirado)\b', text) else 'vencido'
    if re.search(r'\bdni\b.*\bvigente\b', text):
        facts['vigencia'] = 'vigente'
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
        conditions.clear()
    incoming = dict(evidence.condiciones_adulto)
    if evidence.lugar_confirmado:
        if 'adulto_matrimonio' in c['pendientes']:
            incoming.setdefault('matrimonio', 'peru' if evidence.lugar_confirmado == 'peru' else 'extranjero')
        elif 'adulto_defuncion' in c['pendientes']:
            incoming.setdefault('defuncion', evidence.lugar_confirmado)
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
    if op == 'rectificacion' and valor(c, 'vigencia') == 'vencido' and 'renovacion' in c['rechazadas']:
        c['pendientes']['adulto_derivacion'] = 'contradiccion'
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
            if valor(c, 'vigencia') != 'vencido':
                return {}
            return {'dni_mayor_renovacion.txt': {'general'}, 'dni_mayor_rectificacion.txt': {'general', mod}}
        return {'dni_mayor_renovacion.txt': {'general'}}
    result = {'dni_mayor_rectificacion.txt': {'general', mod} - {''}}
    if valor(c, 'vigencia') == 'vencido':
        result['dni_mayor_renovacion.txt'] = {'general'}
    return result


PREGUNTAS = {
    'adulto_derivacion': 'La ficha vincula la rectificación de un DNI vencido con renovación, que ha rechazado. Aclare si solicita también renovación o desea consultar al Consulado antes de continuar.',
    'adulto_modificacion': '¿Desea rectificar datos personales, dirección, imagen o firma, o estado civil?',
    'adulto_transicion': '¿El cambio es a casado, divorciado o viudo?',
    'adulto_matrimonio': '¿El matrimonio se celebró en Perú o fuera de Perú?',
    'adulto_defuncion': '¿La defunción ocurrió en Perú, Italia u otro país?',
    'adulto_italiano': '¿El cónyuge fallecido era italiano? Indique solo sí o no, sin datos identificativos.',
    'adulto_apellido': '¿Desea recuperar el apellido materno? No indique su apellido.',
}
