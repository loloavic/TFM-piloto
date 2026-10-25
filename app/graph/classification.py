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


def solicitante(texto: str, previo: dict) -> tuple[dict, bool, bool]:
    """Solo categoría de edad y destinatario, nunca edad exacta o identidad.

    Una edad del progenitor/documento de apoyo no se asigna al menor. Se busca
    el titular explícito; no se infiere minoría de edad a partir de 'hijo'.
    """
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

    texto = re.sub(r'\b(?:presentar|llevar|mostrar|adjuntar)\s+(?:el\s+)?dni\s+de\s+('
                   + persona + r')', documento, texto)
    if documento_ambiguo:
        # No elegir entre el titular activo y el dueño del documento por inercia.
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


def operacion(texto: str) -> tuple[str, bool, set[str]]:
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
    renewal = bool(re.search(r'\b(?:renovar|renovacion|renuevo|actualizar dni|dni vencido|dni caducado|ya (?:tuvo|tuve|tiene|tengo) (?:un |su )?dni)\b', positive))
    duplicate = bool(re.search(r'\bduplicado\s+(?:(?:de|del|mi|su|el|un)\s+)*dni\b|\bdni duplicado\b', positive))
    if duplicate:
        return ('', True, denied) if first or renewal else ('duplicado', False, denied)
    if re.search(r'\bduplicado\b', positive):
        return '', False, denied | {'sin_objeto'}  # Aclarar objeto antes de heredar.
    return ('primera_vez' if first and not renewal else 'renovacion' if renewal and not first else ''), first and renewal, denied


def clasificar(state: dict) -> dict:
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
    operation, conflict_op, denied = operacion(text)
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
