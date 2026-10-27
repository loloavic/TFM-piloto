"""Reglas deterministas: titular, operación DNI y tema de la pregunta separados.

Los identificadores de adultos/sin edad son clasificación interna, no nuevos
procedimientos disponibles. DOCUMENTADOS enumera las tres rutas del corpus.
"""
import re
import unicodedata

from app.graph.state import EvidenciaTurno
from app.graph.adult_context import extraer as extraer_adulto, respuesta_nacionalidad
from app.graph.context_policy import (
    CAMBIO_AZUL, DOCUMENTADOS, PRIORIDAD, ruta_documental, tramite_candidato, transicionar, validar_contexto,
)

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
        ('fotografias', r'foto'),
        ('requisitos', r'requisitos?|documentos?|\bllevar\b|\bpresentar\b|acompan|apoderad|representante'),
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


def solicitante(texto: str) -> tuple[dict, bool, bool]:
    """Solo categoría de edad y destinatario, nunca edad exacta o identidad.

    Una edad del progenitor/documento de apoyo no se asigna al menor. Se busca
    el titular explícito; no se infiere minoría de edad a partir de 'hijo'.
    """
    texto, documento_ambiguo = identificar_roles(texto)
    if documento_ambiguo:
        return {'grupo_edad': 'desconocido',
                'destinatario': 'desconocido'}, False, True
    # Una negación del grupo no lo convierte en contexto afirmativo.
    texto = re.sub(r'\bno (?:es|soy) (?:para )?(?:un |una )?(?:menor(?: de edad)?|adult[oa]|mayor de edad)\b', ' ', texto)
    child = re.search(r'\b(?:mi|su|el|la|un|una|otro|otra)\s+(hijo|hija|nino|nina|bebe|menor)\b', texto)
    own = bool(re.search(r'\b(?:soy (?:un |una )?(?:adulto|adulta|mayor de edad|menor(?: de edad)?)|tengo \d+ anos|para mi\b|mi dni\b)', texto))
    child_dni = re.search(r'\bdni\s+(?:de|para)\s+(?:(?:mi|su|el|la|un|una)\s+)?(?:hijo|hija|menor|nino|nina|bebe)\b', texto)
    own_positive = re.sub(r'\bno\s+(?:quiero|necesito|debo)\s+(?:renovar|tramitar|solicitar|obtener|sacar)\s+mi\s+dni\b', ' ', texto)
    own_dni = re.search(r'\b(?:renovar|tramitar|solicitar|obtener|sacar)\s+mi\s+dni\b', own_positive)
    # Presentar requisitos no convierte al solicitante explícito en apoyo.
    # Exigir un objeto propio de rectificación; la edad sola no basta.
    own_rectification = re.sub(
        r'\bno\s+(?:quiero|necesito|debo)\s+(?:rectificar|corregir|actualizar|cambiar)\b[^.;?!]*',
        ' ', texto)
    own_civil_update = re.search(
        r'\b(?:actualizar|cambiar|rectificar|corregir)\s+mi\s+estado civil\b', own_rectification)
    own_rectification = re.search(
        r'\b(?:rectificar|corregir)\s+(?:mi\s+(?:dni|fecha de nacimiento|lugar de nacimiento|nombre|apellido|direccion|firma)\b|'
        r'mis\s+(?:datos|nombres|apellidos)\b|datos\s+de\s+mi\s+dni\b)', own_rectification)
    own_dni = own_dni or ((own_rectification or own_civil_update) if re.search(r'\bdni\b', texto) else None)
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
        return {'grupo_edad': 'desconocido',
                'destinatario': 'desconocido'}, False, True
    explicit = False
    target = 'desconocido'
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
    elif re.match(
        r'^(?:mi|su) (?:padre|madre) es (?:mayor de edad|adult[oa]) y '
        r'(?:necesita|quiere) (?:rectificar|corregir) su dni\b', texto
    ):
        # Adulto por afirmación explícita, nunca por el parentesco.
        explicit, target, minor, adult = True, 'adulto', False, True
        segment = ''
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
            r'(?:de|tiene|cumple)\s+(\d{1,3})\s+anos\b', segment,
        )
    elif own:
        ages = re.findall(r'\btengo\s+(\d{1,3})\s+anos\b', texto)
    else:
        ages = re.findall(r'\b(?:de |tiene |tengo )?(\d{1,3}) anos\b', segment)
    # 'menor de 18 años' expresa categoría, no que el titular tenga 18.
    limite = re.search(r'menor de (\d{1,3}) anos', segment)
    if limite:
        ages = []
        minor = int(limite.group(1)) <= 18
        if not minor:
            return {'grupo_edad': 'desconocido', 'destinatario': target}, explicit, True
    if child is None and not own and not explicit:
        ages = []
    age_groups = {('menor' if int(age) < 18 else 'adulto') for age in ages if int(age) <= 120}
    groups = age_groups | ({'menor'} if minor else set()) | ({'adulto'} if adult else set())
    conflict = len(groups) > 1 or any(int(age) > 120 for age in ages)
    group = next(iter(groups)) if len(groups) == 1 else 'desconocido'
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


def operacion(texto: str, contexto_dni: bool = False, *, inferir_tenencia: bool = True) -> tuple[str, bool, set[str]]:
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
    first = bool(re.search(r'primera vez|primera inscripcion|primer dni', positive))
    first = first or (inferir_tenencia and bool(re.search(r'\b(?:nunca (?:(?:ha|he) )?(?:tenido|tuvo|tuve)|no (?:(?:ha|he) tenido|tuvo|tuve)) (?:un |su )?dni\b', positive)))
    renewal = bool(re.search(r'\b(?:renovar|renovacion|renuevo|actualizar dni)\b', positive))
    renewal = renewal or (inferir_tenencia and bool(re.search(
        r'\bya (?:tuvo|tuve|tiene|tengo|tenia) (?:un |su )?dni\b', positive)))
    renewal = renewal or (inferir_tenencia and dni_vencido(texto_roles, contexto_dni) and 'renovacion' not in denied)
    duplicate = bool(re.search(r'\bduplicado\s+(?:(?:de|del|mi|su|el|un)\s+)*dni\b|\bdni duplicado\b', positive))
    if duplicate:
        return ('', True, denied) if first or renewal else ('duplicado', False, denied)
    if re.search(r'\bduplicado\b', positive):
        return '', False, denied | {'sin_objeto'}  # Aclarar objeto antes de heredar.
    return ('primera_vez' if first and not renewal else 'renovacion' if renewal and not first else ''), first and renewal, denied



# El reconocimiento léxico no consulta el contexto ni restaura hechos anteriores.

CONSULTAS = {
    'fotografias': '¿Qué fotografías necesito?',
    'coste': '¿Cuánto cuesta?', 'plazo': '¿Cuánto demora?',
    'cita': '¿Dónde solicito la cita?', 'requisitos': '¿Cuáles son los requisitos?',
    'seguimiento': '¿Cómo consulto el estado del trámite?',
}


def evidencia_color(text: str) -> tuple[str, bool, bool]:
    """Separar el objeto azul de primera inscripción y procesar su negación."""
    positives, denied = [], False
    for clause in re.split(r'[.;?!]|\b(?:pero|sino)\b', text):
        relation = bool(re.search(r'\bamarillo\s+(?:a|al|por|por el)\s+(?:dni\s+)?azul\b', clause)
                        or ('amarillo' in clause and 'azul' in clause and
                            re.search(r'\b(?:cambiar|pasar|sacar|obtener)\b|\bya (?:tengo|tiene)\b', clause)))
        negative = bool(re.search(r'\bno\s+(?:(?:quiero|necesito|deseo|debo|es)\s+)', clause))
        if relation and negative:
            denied = True
        else:
            positives.append(clause)
    positive = ' '.join(positives)
    transition = bool(re.search(r'\bamarillo\s+(?:a|al|por|por el)\s+(?:dni\s+)?azul\b', positive)
                      or ('amarillo' in positive and 'azul' in positive and
                          re.search(r'\b(?:cambiar|pasar|sacar|obtener)\b|\bya (?:tengo|tiene)\b', positive)))
    # No convertir una negación de posesión en prueba de que ya tiene amarillo.
    if re.search(r'\b(?:no tengo|no tiene|nunca tuvo)\b.{0,25}\bamarillo\b', positive):
        transition = False
    return positive, transition, denied


def extraer_evidencia(pregunta: str) -> EvidenciaTurno:
    text = normalizar(pregunta)
    role_text, document_conflict = identificar_roles(text)
    holder, explicit, holder_conflict = solicitante(text)
    positive_color, transition, denied_color = evidencia_color(text)
    blue = bool(re.search(r'\bazul\b', positive_color))
    operation_text = positive_color if denied_color else text
    if re.search(r'\bdomicilio\b', text):
        # Actualizar domicilio no acredita una solicitud de renovación de DNI.
        operation_text = re.sub(r'\bactualizar\b', 'modificar', operation_text)
    _, _, original_denied = operacion(operation_text, contexto_dni=True)
    if blue:
        # Azul por primera vez no implica que nunca haya tenido un DNI.
        operation_text = re.sub(r'\b(?:primera vez|primera inscripcion|primer dni)\b', ' ', operation_text)
    operation, op_conflict, denied = operacion(operation_text, contexto_dni=True)
    denied |= original_denied
    yellow_possession = (bool(re.search(r'\b(?:ya )?(?:tengo|tiene|dispongo de|cuenta con)\b.{0,25}\bamarillo\b', positive_color))
                         and not bool(re.search(r'\bno (?:tengo|tiene)\b', positive_color)))
    explicit_renewal = bool(re.search(r'\b(?:renovar|renovacion|renuevo|actualizar dni)\b', operation_text)) and 'renovacion' not in denied
    if yellow_possession and operation == 'renovacion' and not explicit_renewal:
        operation = ''  # Tener amarillo no selecciona por sí solo renovación ni cambio a azul.
    if denied_color:
        denied.add(CAMBIO_AZUL)
    if transition:
        op_conflict = op_conflict or operation in {'primera_vez', 'duplicado'}
        operation = '' if op_conflict else CAMBIO_AZUL
    adult_facts = extraer_adulto(text)
    if dni_vencido(role_text, True):
        adult_facts = tuple(sorted({**dict(adult_facts), 'vigencia': 'vencido'}.items()))
    neg_rect = bool(re.search(r'\bno (?:quiero|necesito|deseo) (?:rectificar|corregir)\b', text))
    if neg_rect:
        denied.add('rectificacion')
    explicit_rect = bool(re.search(r'\b(?:rectificar|rectificacion|corregir|correccion)\b', text)) and not neg_rect
    if explicit_rect and not neg_rect and (not operation or (
            operation == 'renovacion' and not operacion(operation_text, inferir_tenencia=False)[0])):
        operation = 'rectificacion'
    topic = tipo_consulta(text)
    other_text = re.sub(r'\bno\s+(?:(?:quiero|quiere|necesito|necesita|debo|debe|es|deseo|desea)\s+){0,3}(?:'+ACCION+r'\s+)?'+ART+r'(?:'+OTROS+r')\b', ' ', text)
    dni = bool(re.search(r'\bdni\b|documento nacional de identidad', text))
    other_action = bool(re.search(r'\b'+ACCION+r'\s+'+ART+r'(?:'+OTROS+r')\b', other_text))
    dni_action = bool(re.search(r'\b'+ACCION+r'\s+'+ART+r'dni\b|\bdni\b.*(?:primera vez|renovacion)', other_text))
    support = bool(re.search(r'foto|tamano|\bllevar\b|presentar|documento de apoyo|requisito|\bacta\b|\bpartida\b', text)) or bool(
        {'matrimonio', 'defuncion'} & dict(adult_facts).keys())
    doubts = []
    if holder_conflict:
        if document_conflict:
            doubts.append('documento')
        elif len(re.findall(r'\b(?:mi|su)\s+(?:hijo|hija|menor)\b', role_text)) > 1:
            doubts.append('titular')
        else:
            doubts.append('edad')
    if op_conflict or 'sin_objeto' in denied:
        doubts.append('operacion')
    positive_role = re.sub(r'\bno\s+(?:es\s+)?(?:un\s+)?documento de apoyo\b', ' ', text)
    doc_support = bool(re.search(r'\bdocumento de apoyo\b|\bcomo (?:padre|madre|representante|apoderad[oa])\b|\bpara acompanar\b', positive_role))
    doc_own = bool(re.search(r'\bdni del titular\b|\b(?:mi|su) propio dni\b|\bel dni que (?:quiero|necesito) renovar\b|\bpara (?:su|la) renovacion\b', positive_role))
    role = 'apoyo' if doc_support and not doc_own else 'titular' if doc_own and not doc_support else ''
    asks = topic in CONSULTAS and bool(re.search(r'[¿?]|\b(?:cuanto|donde|cuando|como|cual|que requisitos|dime|quiero saber)\b', text))
    if role and not re.search(r'[¿?]|\b(?:dime|quiero saber)\b', text):
        asks = False
    possession = dni_vencido(role_text, True) or bool(re.search(
        r'\bya (?:tuvo|tuve|tiene|tengo|tenia) (?:un |su )?dni\b|'
        r'\bnunca (?:(?:ha|he) )?(?:tenido|tuvo|tuve) (?:un |su )?dni\b', text))
    request = (bool(operation and re.search(r'\b(?:quiero|necesito|solicito|renovar|renovacion)\b', text))
               or doc_own or bool(explicit and re.search(r'\bpara (?:mi|su|el|la)\b', text)))
    # Extraer por separado la operación afirmada, sin inferencias de tenencia.
    # Reutilizar el detector mantiene su tratamiento de negaciones y conflictos.
    affirmative_operation = operacion(operation_text, inferir_tenencia=False)[0]
    if explicit_rect and operation == 'rectificacion':
        affirmative_operation = 'rectificacion'
    if transition and not op_conflict and re.search(
            r'\b(?:cambiar|pasar|sacar|obtener)\b', positive_color):
        # La operación específica también puede solicitarse afirmativamente;
        # mencionar tenencia junto a esa petición no la convierte en observación.
        affirmative_operation = CAMBIO_AZUL
    return EvidenciaTurno(
        condiciones_adulto=adult_facts,
        respuesta_nacionalidad=respuesta_nacionalidad(text),
        lugar_confirmado=next((place for word, place in [('peru','peru'),('italia','italia'),('otro pais','otro')]
            if re.fullmatch(r'(?:fue |ocurrio )?en (?:el )?' + word + r'[.!]?', text)), ''),
        respuesta_binaria='si' if re.fullmatch(r'si[.!]?', text) else 'no' if re.fullmatch(r'no[.!]?', text) else '',
        titular=holder['destinatario'] if explicit and not holder_conflict and holder['destinatario'] != 'desconocido' else '',
        edad=holder['grupo_edad'] if not holder_conflict and holder['grupo_edad'] != 'desconocido' else '',
        operacion=operation, rechazadas=tuple(sorted(denied - {'sin_objeto'})), dudas=tuple(doubts),
        tema=topic, pregunta_tema=asks, dni=dni,
        otro_tramite=other_action, otro_solo=bool(re.fullmatch(r'(?:'+OTROS+r')[?.!]*', other_text)),
        otro_necesitado=bool(re.search(r'\b(?:necesito|quiero|busco|deseo)\s+'+ART+r'(?:'+OTROS+r')\b', other_text)),
        mencion_otro=bool(re.search(r'\b(?:'+OTROS+r')\b', other_text)), apoyo=support,
        finalidad_dni=bool(re.search(r'\bpara\b.{0,55}\bdni\b', other_text)), mixto=other_action and dni_action,
        funcion_documento=role,
        cambio=bool(re.search(r'\b(?:ahora|en cambio|otro|otra|olvida|olvidemos|me equivoque|en realidad|sin renovar|solo rectificar)\b', text)),
        rectificacion=bool(re.search(r'\b(?:me equivoque|en realidad)\b', text)),
        otro_titular=bool(re.search(r'\b(?:otro|otra)\b', text)), solicitud=request,
        # Identificar al destinatario o la función documental no convierte
        # una observación de tenencia en una solicitud de operación.
        observacion=possession and affirmative_operation != operation,
        referencia_azul=blue,
        tiene_amarillo=yellow_possession,
        nunca_tuvo_dni=bool(re.search(r'\b(?:nunca (?:(?:ha|he) )?(?:tenido|tuvo|tuve)|no (?:(?:ha|he) tenido|tuvo|tuve)) (?:un |su )?dni\b', text)),
        abandonar=bool(re.fullmatch(r'(?:olvida|olvidemos|cancela|dejemos) (?:lo anterior|la consulta|la aclaracion)[.!]?', text)),
    )


def proyectar(c: dict) -> dict:
    """Contrato legado como salida; ninguna transición vuelve a leerlo."""
    pending = c['pendientes']
    reason = next((p for p in PRIORIDAD if p in pending), '')
    candidate = tramite_candidato(c)
    active = c['ultima_ruta'] if pending else candidate if c['ambito'] == 'dni' else ''
    route = ruta_documental(c)
    intent = 'fuera_alcance' if c['ambito'] == 'fuera_alcance' else 'general' if pending else route or 'general'
    status = ('fuera_alcance' if intent == 'fuera_alcance' else 'pendiente_aclaracion' if pending
              else 'disponible' if route else 'no_documentado')
    operation = c['operacion']['valor']
    if 'documento' in pending or operation in c['rechazadas']:
        operation = ''
    holder = {} if c['ambito'] == 'fuera_alcance' or 'titular' in pending else {
        'grupo_edad': c['edad']['valor'] or 'desconocido',
        'destinatario': c['titular']['valor'] or 'desconocido',
    }
    evidence = ['operacion:' + c['operacion']['valor']] if c['operacion']['turno'] == c['turno'] and c['operacion']['valor'] else []
    evidence += ['rechazo_vigente:' + op for op in c['rechazadas']]
    return {'intencion': intent, 'tramite_actual': active, 'operacion_dni': operation,
            'contexto_solicitante': holder, 'tipo_consulta': c['tema'],
            'requiere_aclaracion': bool(pending), 'motivo_aclaracion': reason,
            'tramite_documentado': not pending and active in DOCUMENTADOS,
            'estado_documental': status,
            'decision': {'tramite_candidato': candidate, 'evidencias': evidence,
                         'faltantes': [p for p in PRIORIDAD if pending.get(p) == 'faltante'],
                         'contradicciones': [p for p in PRIORIDAD if pending.get(p) == 'contradiccion'],
                         'consulta_pendiente': c['consulta_pendiente'] or c['retomar']}}


def clasificar(state: dict) -> dict:
    c = transicionar(state.get('contexto_canonico'), extraer_evidencia(state['pregunta']))
    return {**state, **proyectar(c), 'contexto_canonico': c,
            'pregunta': state['pregunta'].strip(), 'intencion_anterior': state.get('intencion', '')}


def pregunta_contextual(state: dict) -> str:
    c = state.get('contexto_canonico')
    pending = c['retomar'] if c and validar_contexto(c) and not c['pendientes'] else ''
    if pending in CONSULTAS:
        return f'Consulta pendiente: {CONSULTAS[pending]}\nAclaración recibida: {state["pregunta"]}'
    return state['pregunta']
