"""Reglas deterministas: titular, operación DNI y tema de la pregunta separados.

Los identificadores de adultos/sin edad son clasificación interna, no nuevos
procedimientos disponibles. DOCUMENTADOS enumera las tres rutas del corpus.
"""
import re
import unicodedata

DOCUMENTADOS = {'dni_menor_renovacion', 'dni_menor_primera_vez', 'dni_consulta_estado'}
OTROS = r'pasaporte|visa|visado|apostilla|matrimonio|defuncion|carta poder|poder consular|licencia de conducir|carnet de extranjeria'
ART = r'(?:(?:un|una|el|la|mi|su)\s+)?'
ACCION = r'(?:renovar|tramitar|solicitar|obtener|sacar|renovacion (?:de|del)|inscripcion (?:de|del))'


def normalizar(texto: str) -> str:
    return ' '.join(''.join(c for c in unicodedata.normalize('NFD', texto.casefold())
                           if unicodedata.category(c) != 'Mn').split())


def tipo_consulta(texto: str) -> str:
    texto = re.sub(r'\bno\s+(?:(?:quiero|necesito|deseo)\s+)?(?:consultar|saber|ver)\s+(?:el\s+)?(?:estado(?: del tramite)?|seguimiento)\b', ' ', texto)
    temas = (
        ('seguimiento', r'estado (?:de|del)|seguimiento|avance|(?:aun|todavia) no (?:ha )?llegado|ya (?:esta listo|llego)|si (?:esta listo|(?:ya )?llego)|recoger (?:mi|el|su) dni|observad[oa]|subsanad[oa]|numero de ficha|100\s*%'),
        ('plazo', r'cuanto (?:demora|tarda)|cuando (?:llega|llegara|estara listo)|tiempo (?:estimado|de entrega)|plazo|demora|tarda'),
        ('cita', r'\bcita\b|reservar|reserva|horarios?|turnos?|bookeo'),
        ('coste', r'\bcost[oe]\b|cuanto cuesta|precio|\bpago\b|\btasa\b|\bmonto\b|importe'),
        ('requisitos', r'requisitos?|foto|documentos?|\bllevar\b|\bpresentar\b|acompan|apoderad|representante'),
    )
    return next((tema for tema, pattern in temas if re.search(pattern, texto)), 'otra')


def identificar_roles(texto: str) -> tuple[str, bool]:
    """Texto relativo al titular y señal de ambigüedad documental."""
    # Excluir personas con un rol de apoyo explícito antes de buscar al titular.
    # Solo se enmascara la mención vinculada al rol, no todo el enunciado:
    # puede contener también al menor cuyo DNI se solicita. Esto no autoriza
    # al acompañante a representar legalmente al titular.
    persona = (r'\b(?:mi|su|el|la|un|una)\s+'
               r'(?:hijo|hija|nino|nina|bebe|menor|padre|madre|adulto|adulta)\b'
               r'(?:\s+(?:de\s+\d{1,3}\s+anos|menor(?: de edad)?|adult[oa]))?')
    roles = (
        r'\bacompan(?:arlo|arla|arme|arte|arles|arnos|ar)\s+(' + persona + r')',
        r'\bacompanad[oa]\s+por\s+(' + persona + r')',
        r'(' + persona + r')\s+(?:(?:puede|debe|podria)\s+)?acompan(?:arlo|arla|arme|arte|arles|arnos|ar)\b',
        r'(' + persona + r')\s+(?:como|(?:puede|debe|podria)\s+ser)\s+(?:acompanante|representante(?: legal)?|apoderad[oa])\b',
    )
    for patron in roles:
        texto = re.sub(patron, lambda m: m.group(0)[:m.start(1) - m.start()] +
                       ' persona de apoyo ' + m.group(0)[m.end(1) - m.start():], texto)
    # Presentar un DNI no implica que sea un documento de apoyo. Examinar
    # la finalidad local antes de excluir a la persona o actualizar el titular.
    documento_ambiguo = False

    def documento(match: re.Match) -> str:
        nonlocal documento_ambiguo
        finalidad = re.split(r'[.;?!]', texto[match.end():], maxsplit=1)[0]
        apoyo = bool(re.search(
            r'\bcomo (?:documento de apoyo|padre|madre|representante|apoderad[oa])\b|'
            r'\bpara acompanar\b', finalidad))
        propio = bool(re.search(r'\bpara (?:su|la) renovacion\b|\bpara renovar(?:lo|la)?\b', finalidad))
        if apoyo and not propio:
            return match.group(0)[:match.start(1) - match.start()] + ' persona de apoyo '
        if not propio or apoyo:
            documento_ambiguo = True
        return match.group(0)

    texto = re.sub(r'\b(?:presentar|llevar|mostrar|adjuntar)\s+(?:el\s+)?dni'
                   r'(?:\s+(?:vencido|caducado|expirado|vigente))?\s+de\s+('
                   + persona + r')', documento, texto)
    return texto, documento_ambiguo


def solicitante(texto: str, previo: dict) -> tuple[dict, bool, bool]:
    """Solo categoría de edad y destinatario, nunca edad exacta o identidad.

    Una edad del progenitor/documento de apoyo no se asigna al menor. Se busca
    el titular explícito; no se infiere minoría de edad a partir de 'hijo'.
    """
    texto, documento_ambiguo = identificar_roles(texto)
    if documento_ambiguo:
        return {'grupo_edad': previo.get('grupo_edad', 'desconocido'),
                'destinatario': previo.get('destinatario', 'desconocido')}, False, True
    # Una negación del grupo no lo convierte en contexto afirmativo.
    texto = re.sub(r'\bno (?:es|soy) (?:para )?(?:un |una )?(?:menor(?: de edad)?|adult[oa]|mayor de edad)\b', ' ', texto)
    child = re.search(r'\b(?:mi|su|el|la|un|una|otro|otra)\s+(hijo|hija|nino|nina|bebe|menor)\b', texto)
    own = bool(re.search(r'\b(?:soy (?:un |una )?(?:adulto|adulta|mayor de edad|menor(?: de edad)?)|tengo \d+ anos|para mi\b|mi dni\b)', texto))
    child_dni = re.search(r'\bdni\s+(?:de|para)\s+(?:(?:mi|su|el|la|un|una)\s+)?(?:hijo|hija|menor|nino|nina|bebe)\b', texto)
    own_positive = re.sub(r'\bno\s+(?:quiero|necesito|debo)\s+(?:renovar|tramitar|solicitar|obtener|sacar)\s+mi\s+dni\b', ' ', texto)
    own_dni = re.search(r'\b(?:renovar|tramitar|solicitar|obtener|sacar)\s+mi\s+dni\b', own_positive)
    if child_dni and own_dni and re.search(
        r'\bno\s+(?:quiero|necesito|debo)\s+' + ACCION + r'\s+' + ART + r'$',
        texto[:child_dni.start()],
    ):
        child_dni = None  # El titular negado no gana al objeto afirmativo.
    own_segment = texto
    if own_dni and child and not child_dni:
        own_segment = texto[:child.start()]
        child = None
    if not own_dni and re.search(r'\b(?:llevar|presentar|mostrar|adjuntar|fotocopia)\b', texto):
        # El DNI de quien acompaña es apoyo documental, no un cambio de titular.
        own = False
    if (len(re.findall(r'\b(?:mi|su|el|la|un|una|otro|otra)\s+(?:hijo|hija|menor|nino|nina)\b', texto)) > 1
            or (own_dni and child_dni and ' y ' in texto)):
        return {'grupo_edad': previo.get('grupo_edad', 'desconocido'),
                'destinatario': previo.get('destinatario', 'desconocido')}, False, True
    explicit = False
    target = previo.get('destinatario', 'desconocido')
    segment = texto
    if child:
        explicit, target = True, 'descendiente' if child.group(1) in {'hijo', 'hija'} else 'menor'
        # No tomar edades que aparezcan antes del titular ni en otro enunciado.
        segment = re.split(r'[.;?!]|\b(?:con su padre|con un adulto|acompanado por)\b', texto[child.end():], maxsplit=1)[0]
        segment = segment[:100]
        minor = child.group(1) in {'nino', 'nina', 'bebe', 'menor'} or bool(re.match(r'\s*(?:que es |es )?(?:menor\b|menor de edad\b)', segment))
        adult = bool(re.match(r'\s*(?:que es |es )?(?:adult[oa]\b|mayor de edad\b)', segment))
    elif re.search(r'\b(?:para (?:un|una) menor|dni (?:(?:de|para) )?(?:un |una )?menor|dni de menor)\b', texto):
        explicit, target, minor, adult = True, 'menor', True, False
    elif own:
        explicit, target = True, 'propio'
        segment = own_segment
        minor = bool(re.search(r'\bsoy (?:(?:un|una) )?menor(?: de edad)?\b|\bmi dni de menor\b', texto))
        adult = bool(re.search(r'\bsoy (?:(?:un|una) )?(?:persona )?(?:adult[oa]|mayor de edad)\b|\bmi dni de adult[oa]\b', texto))
    elif re.search(r'\b(?:para (?:un|una) adult[oa]|dni de adult[oa])\b', texto):
        explicit, target, minor, adult = True, 'adulto', False, True
    else:
        # Respuesta a una aclaración sobre el titular, no sobre acompañantes.
        standalone = re.fullmatch(r'(?:es |soy |tiene |tengo )?(?:un |una )?(?:menor(?: de edad)?|adult[oa]|mayor de edad|\d{1,3} anos)[.!]?', texto)
        minor = bool(standalone and re.search(r'\bmenor\b', texto))
        adult = bool(standalone and re.search(r'adult|mayor de edad', texto))
        if standalone:
            explicit = True
    if child:
        # Solo edades unidas gramaticalmente al titular, no al acompañante.
        ages = re.findall(
            r'^\s*,?\s*(?:que\s+)?(?:(?:es\s+)?(?:menor(?: de edad)?|adult[oa]|mayor de edad)\s+)?'
            r'(?:de|tiene)\s+(\d{1,3})\s+anos\b', segment,
        )
    elif own:
        ages = re.findall(r'\btengo\s+(\d{1,3})\s+anos\b', texto)
    else:
        ages = re.findall(r'\b(?:de |tiene |tengo )?(\d{1,3}) anos\b', segment)
    # 'menor de 18 años' expresa categoría, no que el titular tenga 18.
    if re.search(r'menor de 18 anos', segment):
        minor = True
        ages = []
    if child is None and not own and not explicit:
        ages = []
    age_groups = {('menor' if int(age) < 18 else 'adulto') for age in ages if int(age) <= 120}
    groups = age_groups | ({'menor'} if minor else set()) | ({'adulto'} if adult else set())
    conflict = len(groups) > 1 or any(int(age) > 120 for age in ages)
    group = next(iter(groups)) if len(groups) == 1 else 'desconocido'
    if not groups and not conflict and target == previo.get('destinatario'):
        group = previo.get('grupo_edad', 'desconocido')
    return {'grupo_edad': group, 'destinatario': target}, explicit, conflict


def dni_vencido(texto: str, contexto_dni: bool = False) -> bool:
    """Evidencia de tenencia, limitada al DNI y nunca a otro documento."""
    texto = re.sub(r'\b(?:no|tampoco)\s+(?:(?:esta|ha|se)\s+)?'
                   r'(?:vencid[oa]|caducad[oa]|expirad[oa]|vencio|caduco|expiro)\b', ' ', texto)
    if re.search(r'\b(?:pasaporte|visa|foto|documento de apoyo|persona de apoyo|padre|madre|representante|acompanante)\b', texto):
        return False
    estado = r'(?:vencid[oa]|caducad[oa]|expirad[oa]|vencio|caduco|expiro)'
    if re.search(r'\bdni\b[^.;?!]{0,80}\b' + estado + r'\b', texto):
        return True
    return bool(contexto_dni and re.fullmatch(
        r'[¿¡]?(?:(?:su|mi|el) dni )?(?:(?:ya|esta|ha|se|me|le)\s+){1,3}'
        + estado + r'[.!?]?', texto))


def operacion(texto: str, contexto_dni: bool = False) -> tuple[str, bool, set[str]]:
    # Las operaciones expresadas como solicitud se conservan, pero el estado
    # de un documento de apoyo no prueba tenencia del DNI del titular.
    texto_roles, _ = identificar_roles(texto)
    # La máscara elimina solo la expresión negada, no su corrección posterior.
    neg_renew = r'\b(?:no|tampoco)\s+(?:(?:quiero|quiere|necesito|necesita|debo|debe|corresponde|es|deseo|desea)\s+){0,3}(?:(?:un|una|la|el)\s+)?(?:renovar(?:lo)?|renovacion|renuevo|actualizar)(?:\s+(?:el |mi |su )?dni)?\b'
    neg_first = (r'\b(?:no|tampoco)\s+(?:(?:quiero|quiere|necesito|necesita|debo|debe|es|corresponde)\s+){0,3}'
                 r'(?:(?:tramitar|solicitar|sacar|obtener)\s+)?'
                 r'(?:(?:el|un|su|mi|la)\s+)?(?:dni\s+)?(?:por\s+)?'
                 r'(?:primera vez|primera inscripcion|primer dni)\b')
    neg_duplicate = r'\b(?:no|tampoco)\s+(?:(?:quiero|necesito|es)\s+){0,3}(?:un |el )?duplicado(?:\s+(?:de |del )?dni)?\b'
    denied = {nombre for nombre, patron in (
        ('duplicado', neg_duplicate), ('renovacion', neg_renew), ('primera_vez', neg_first)
    ) if re.search(patron, texto)}
    texto = re.sub(neg_duplicate, ' ', texto)
    positive = re.sub(neg_first, ' ', re.sub(neg_renew, ' ', texto))
    first = bool(re.search(r'primera vez|primera inscripcion|primer dni|\b(?:nunca (?:(?:ha|he) )?(?:tenido|tuvo|tuve)|no (?:(?:ha|he) tenido|tuvo|tuve)) (?:un |su )?dni\b', positive))
    renewal = bool(re.search(r'\b(?:renovar|renovacion|renuevo|actualizar dni|ya (?:tuvo|tuve|tiene|tengo|tenia) (?:un |su )?dni)\b', positive))
    renewal = renewal or (dni_vencido(texto_roles, contexto_dni) and 'renovacion' not in denied)
    duplicate = bool(re.search(r'\bduplicado\s+(?:(?:de|del|mi|su|el|un)\s+)*dni\b|\bdni duplicado\b', positive))
    if duplicate:
        return ('', True, denied) if first or renewal else ('duplicado', False, denied)
    if re.search(r'\bduplicado\b', positive):
        return '', False, denied | {'sin_objeto'}  # Aclarar objeto antes de heredar.
    return ('primera_vez' if first and not renewal else 'renovacion' if renewal and not first else ''), first and renewal, denied


def _clasificar_candidato(state: dict) -> dict:
    pregunta = state['pregunta'].strip()
    text = normalizar(pregunta)
    previous = state.get('tramite_actual', '')
    context = state.get('contexto_solicitante', {})
    previous_op = state.get('operacion_dni', '')
    topic = tipo_consulta(text)
    # Negaciones de otros trámites no convierten la consulta en fuera de alcance.
    other_text = re.sub(r'\bno\s+(?:(?:quiero|quiere|necesito|necesita|debo|debe|es|deseo|desea)\s+){0,3}(?:'+ACCION+r'\s+)?'+ART+r'(?:'+OTROS+r')\b', ' ', text)
    other_action = bool(re.search(r'\b'+ACCION+r'\s+'+ART+r'(?:'+OTROS+r')\b', other_text))
    other_need = bool(re.search(r'\b(?:necesito|quiero|busco|deseo)\s+'+ART+r'(?:'+OTROS+r')\b', other_text))
    other_bare = bool(re.fullmatch(r'(?:'+OTROS+r')[?.!]*', other_text))
    # 'necesito pasaporte para el DNI' es un requisito; 'renovar pasaporte' es otro trámite.
    dni = bool(re.search(r'\bdni\b|documento nacional de identidad', text))
    dni_action = bool(re.search(r'\b'+ACCION+r'\s+'+ART+r'dni\b|\bdni\b.*(?:primera vez|renovacion)', other_text))
    foreign = bool(re.search(r'\b(?:'+OTROS+r')\b', other_text))
    support = bool(re.search(r'foto|tamano|\bllevar\b|presentar|documento de apoyo|requisito', text))
    purpose_dni = bool(re.search(r'\bpara\b.{0,55}\bdni\b', other_text))
    other_action = other_action or (other_need and not purpose_dni and not support and not previous)
    other_action = other_action or (foreign and not dni and topic == 'seguimiento')
    mixed = other_action and dni_action
    if (other_action or (other_bare and not previous) or (other_need and not dni and not previous) or (foreign and not dni and not previous and not support)) and not mixed:
        return {**state, 'pregunta': pregunta, 'intencion_anterior': state.get('intencion', ''),
                'intencion': 'fuera_alcance', 'tramite_actual': '', 'operacion_dni': '',
                'contexto_solicitante': {}, 'tipo_consulta': topic,
                'requiere_aclaracion': False, 'motivo_aclaracion': '',
                'tramite_documentado': False, 'estado_documental': 'fuera_alcance'}

    holder, explicit_holder, conflict_age = solicitante(text, context)
    if explicit_holder and re.search(r'\b(?:ahora|otro|otra|en cambio)\b', text):
        holder, _, conflict_age = solicitante(text, {})
    operation, conflict_op, denied = operacion(text, bool(previous))
    scope = dni or bool(previous)
    if not scope:
        operation = ''
    if not operation and not conflict_op and previous_op not in denied and 'sin_objeto' not in denied:
        # No trasladar una operación a un titular nuevo por mera inercia.
        changed_holder = (explicit_holder and context.get('destinatario', 'desconocido') != 'desconocido'
                          and holder['destinatario'] != context.get('destinatario'))
        operation = '' if changed_holder else previous_op
    if mixed or conflict_op or conflict_age:
        operation = ''
    group = holder['grupo_edad']
    reason = ''
    if mixed or conflict_op or conflict_age:
        reason = 'contradiccion'
    elif not scope or (foreign and not dni and not support):
        reason = 'tramite'
    elif not operation and topic != 'seguimiento':
        reason = 'operacion'
    elif operation in {'renovacion', 'primera_vez'} and group == 'desconocido':
        reason = 'edad'

    if operation == 'duplicado':
        active = 'dni_duplicado'  # Identificado, sin habilitar nueva documentación.
    elif operation:
        beneficiary = group if group in {'menor', 'adulto'} else 'sin_edad'
        active = f'dni_{beneficiary}_{operation}'
    elif scope and not reason and topic == 'seguimiento':
        active = previous or 'dni_consulta_estado'
    else:
        active = 'dni_por_aclarar' if scope else ''
    documented = active in DOCUMENTADOS
    # Tema seguimiento no reemplaza la operación; solo selecciona su fuente.
    if topic == 'seguimiento' and scope and not (mixed or conflict_op or conflict_age):
        intent, status, reason = 'dni_consulta_estado', 'disponible', ''
        active = active or 'dni_consulta_estado'
    elif reason:
        intent, status = 'general', 'pendiente_aclaracion'
    elif documented:
        intent, status = active, 'disponible'
    else:
        intent, status = 'general', 'no_documentado'
    return {**state, 'pregunta': pregunta, 'intencion_anterior': state.get('intencion', ''),
            'intencion': intent, 'tramite_actual': active, 'operacion_dni': operation,
            'contexto_solicitante': holder, 'tipo_consulta': topic,
            'requiere_aclaracion': bool(reason), 'motivo_aclaracion': reason,
            'tramite_documentado': documented, 'estado_documental': status}


CONSULTAS = {
    'coste': '¿Cuánto cuesta?', 'plazo': '¿Cuánto demora?',
    'cita': '¿Dónde solicito la cita?', 'requisitos': '¿Cuáles son los requisitos?',
    'seguimiento': '¿Cómo consulto el estado del trámite?',
}


def _operacion_confirmada(tramite: str) -> str:
    return next((op for op in ('primera_vez', 'renovacion', 'duplicado')
                 if tramite.endswith('_' + op)), '')


def clasificar(state: dict) -> dict:
    """Proponer, contrastar y confirmar; una hipótesis no sustituye el activo.

    La decisión conserva códigos de evidencia y tema pendiente, nunca una
    segunda copia de la pregunta ni nuevos datos personales. Los campos
    requiere_aclaracion/motivo_aclaracion son la única puerta de confirmación.
    """
    text = normalizar(state['pregunta'])
    if re.fullmatch(r'(?:olvida|olvidemos|cancela|dejemos) (?:lo anterior|la consulta|la aclaracion)[.!]?', text):
        state = {**state, 'tramite_actual': '', 'operacion_dni': '',
                 'contexto_solicitante': {}, 'tipo_consulta': 'otra',
                 'requiere_aclaracion': False, 'decision': {}}
    previous = state.get('tramite_actual', '')
    pending = state.get('decision', {})
    waiting = state.get('requiere_aclaracion', False)
    # Dar contexto a las aclaraciones sin presentar la hipótesis como confirmada.
    working = {**state, 'tramite_actual': previous or pending.get('tramite_candidato', '')}
    result = _clasificar_candidato(working)
    if result['intencion'] == 'fuera_alcance':
        return {**result, 'decision': {
            'tramite_candidato': '', 'evidencias': ['fuera_alcance'],
            'faltantes': [], 'contradicciones': [], 'consulta_pendiente': '',
        }}

    operation, conflict, denied = operacion(text, bool(working['tramite_actual']))
    holder, explicit_holder, conflict_holder = solicitante(text, state.get('contexto_solicitante', {}))
    changed = bool(re.search(r'\b(?:ahora|en cambio|otro|otra|olvida|olvidemos|me equivoque|en realidad)\b', text))
    topic = tipo_consulta(text)
    explicit_change = changed and bool(operation or explicit_holder or topic == 'seguimiento') and not (conflict or conflict_holder)
    evidence = []
    if operation:
        evidence.append('operacion:' + operation)
    evidence.extend('negacion:' + op for op in sorted(denied))
    if explicit_holder:
        evidence.append('titular_explicito')
    if previous:
        evidence.append('contexto_confirmado')
    possession = dni_vencido(text, bool(previous)) or bool(re.search(
        r'\bya (?:tuvo|tuve|tiene|tengo|tenia) (?:un |su )?dni\b|'
        r'\bnunca (?:(?:ha|he) )?(?:tenido|tuvo|tuve) (?:un |su )?dni\b', text))
    if possession:
        evidence.append('tenencia_dni')
    candidate = result['tramite_actual']
    reason = result['motivo_aclaracion']
    if conflict:
        reason = 'operacion'
    if conflict_holder:
        if len(re.findall(r'\b(?:mi|su)\s+(?:hijo|hija|menor)\b', text)) > 1:
            reason = 'titular'
        elif re.search(r'\b(?:presentar|llevar|mostrar|adjuntar)\b', text):
            reason = 'documento'
        else:
            reason = 'edad'
    prior_reason = state.get('motivo_aclaracion', '')
    answer = bool(operation or (explicit_holder and not conflict_holder))
    # Preguntar por coste/estado no confirma ninguno de los datos en disputa.
    if waiting and not explicit_change:
        resolves = answer and not (conflict or conflict_holder)
        if prior_reason in {'dni_previo', 'operacion'}:
            resolves = bool(operation) and not (conflict or conflict_holder)
        if prior_reason == 'edad':
            resolves = explicit_holder and holder['grupo_edad'] != 'desconocido' and not conflict_holder
        if prior_reason == 'tramite':
            resolves = bool(re.search(r'\bdni\b', text)) and not (conflict or conflict_holder)
        if not resolves:
            reason = prior_reason
            candidate = pending.get('tramite_candidato', candidate)

    old_operation = _operacion_confirmada(previous)
    # Un hecho incompatible pide confirmación; una solicitud/rectificación
    # inequívoca o respuesta a la aclaración puede cambiar el procedimiento.
    if (possession and operation and old_operation and operation != old_operation
            and not waiting and not explicit_change and old_operation not in denied
            and not re.search(r'\b(?:quiero|necesito|solicito|renovar|renovacion)\b', text)):
        reason = 'dni_previo'

    pending_topic = pending.get('consulta_pendiente', '') if waiting and not explicit_change else ''
    if reason:
        pending_topic = topic if topic in CONSULTAS else pending_topic
        # El tópico anterior sigue pendiente al detectarse una contradicción.
        pending_topic = pending_topic or (state.get('tipo_consulta', '') if state.get('tipo_consulta') in CONSULTAS else 'otra')
        if previous:
            result['tramite_actual'] = previous
            # No reemplazar al titular confirmado por un candidato contradictorio.
            if reason in {'dni_previo', 'titular', 'documento', 'contradiccion'}:
                result['contexto_solicitante'] = state.get('contexto_solicitante', {})
            if reason == 'edad' and conflict_holder:
                result['contexto_solicitante'] = state.get('contexto_solicitante', {})
                # La duda es de edad: no perder además una operación confirmada
                # que el ciudadano no ha rechazado.
                if old_operation not in denied and not conflict:
                    result['operacion_dni'] = state.get('operacion_dni', old_operation)
        else:
            result['tramite_actual'] = ''
        if reason == 'dni_previo':
            result['operacion_dni'] = state.get('operacion_dni', old_operation)
        result.update(intencion='general', requiere_aclaracion=True,
                      motivo_aclaracion=reason, tramite_documentado=False,
                      estado_documental='pendiente_aclaracion')
    elif waiting and pending_topic and topic == 'otra':
        result['tipo_consulta'] = pending_topic
        if pending_topic == 'seguimiento':
            result.update(intencion='dni_consulta_estado', estado_documental='disponible')
    else:
        pending_topic = ''

    contradictions = [reason] if reason and (conflict or conflict_holder or reason not in {'edad', 'operacion', 'tramite'}) else []
    if reason and not contradictions and waiting and reason == prior_reason:
        contradictions = pending.get('contradicciones', [])
    result['decision'] = {
        'tramite_candidato': candidate,
        'evidencias': evidence,
        'faltantes': [reason] if reason in {'edad', 'operacion', 'tramite'} and not contradictions else [],
        'contradicciones': contradictions,
        'consulta_pendiente': pending_topic,
    }
    return result


def pregunta_contextual(state: dict) -> str:
    """Recuperar un tema aclarado incluso si salió del historial limitado."""
    pending = state.get('decision', {}).get('consulta_pendiente', '')
    if not state.get('requiere_aclaracion') and pending in CONSULTAS:
        return f'Consulta pendiente: {CONSULTAS[pending]}\nAclaración recibida: {state["pregunta"]}'
    return state['pregunta']
