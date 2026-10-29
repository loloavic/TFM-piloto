"""Presentación determinista de textos ya autorizados; sin inferir hechos."""
import re

from app.graph.classification import consulta_elegibilidad


def texto_ciudadano(text):
    replacements = {
        'La ficha PDF específica no indica cantidad de fotos; el plazo común se registra por separado.':
            'Confirme con el Consulado la cantidad de fotografías que debe llevar.',
        'No se confirma combinación con renovación ni suma de tasas.':
            'Si también necesita renovar, confirme con el Consulado cómo realizar ambos trámites y cuánto debe pagar.',
        'La ficha no aclara antigüedad máxima de esa copia consular.':
            'Consulte con el Consulado la antigüedad admitida para esa copia.',
        'Aplicar las condiciones generales de documentos peruanos.':
            'Para documentos emitidos en Perú, respete las condiciones indicadas anteriormente.',
        'Si se emitió en Perú, aplicar las condiciones generales de documentos peruanos.':
            'Si se emitió en Perú, respete las condiciones indicadas anteriormente.',
        'Aplicar condiciones generales de actas peruanas.':
            'Para las actas emitidas en Perú, respete las condiciones indicadas en esta respuesta.',
        'La ficha permite cambio de dirección; no detalla documentos adicionales.':
            'Puede solicitar el cambio de dirección. Confirme con el Consulado qué documentación adicional necesita.',
        'La ficha permite cambio de imagen o firma; no detalla otros documentos adicionales.':
            'Puede solicitar el cambio de imagen o firma. Confirme con el Consulado qué documentación adicional necesita.',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def condiciones_civiles(general):
    """Conservar completas las condiciones generales y agrupar las fotografías."""
    general = texto_ciudadano(general)
    # El detalle permanece en la respuesta, desplegable en Gradio. No se recorta
    # ninguna característica requerida ni se delega su reescritura al modelo.
    photo = re.search(r'Fotografía obligatoria:.*?(?= Confirme con el Consulado la cantidad)', general)
    if photo:
        details = ('<details><summary>Características obligatorias de las fotografías</summary>\n\n'
                   + photo[0] + '\n\n</details>')
        general = general[:photo.start()] + general[photo.end():]
    else:
        details = ''
    return general.strip(), details


def apartado_apellido(surname, decision=''):
    if not surname or decision == 'no':
        return ''
    label = 'Recuperación del apellido materno solicitada' if decision == 'si' else 'Recuperación del apellido materno (solo si la necesita)'
    return '**' + label + '**\n\n' + texto_ciudadano(surname.strip()).replace('indicadas anteriormente', 'indicadas en esta respuesta')


def requisitos_civiles(general, principal, surname='', decision='', tramite='divorcio'):
    general, details = condiciones_civiles(general)
    parts = ['Para actualizar su DNI por ' + tramite + ':', principal,
             apartado_apellido(surname, decision), '**Condiciones del trámite**\n\n' + general, details]
    return '\n\n'.join(p for p in parts if p)


def requisitos_viudez(general, marriage, death, surname='', decision=''):
    principal = '- **Defunción:** ' + death.strip() + '\n\n- **Matrimonio:** ' + marriage.strip()
    return requisitos_civiles(general, principal, surname, decision, 'viudez')


def incertidumbre_viudez(state):
    """No convertir una lista ambigua de actas en obligaciones."""
    rules = {f.get('metadata', {}).get('regla'): f['contenido'] for f in state.get('fragmentos', [])}
    if 'viudez_italia' in rules:
        return ('No puedo confirmar todavía qué documento de defunción debe presentar en su caso, '
                'ni si el acta original y la certificación consular se sustituyen o deben presentarse juntas. '
                'Confirme este punto con el Consulado antes de acudir. '
                'No aplique automáticamente los requisitos de otra nacionalidad. '
                'La acreditación del matrimonio es independiente de la defunción.')
    return ('No puedo confirmar los documentos específicos de defunción para ese país. '
            'Consulte con el Consulado qué actas debe presentar antes de acudir. '
            'Los requisitos del caso italiano no se aplican automáticamente a su situación.')


ACLARACION_VIGENCIA = ('¿El DNI está vencido, vence dentro de 60 días o menos, '
                       'o le quedan más de 60 días? No indique la fecha exacta.')


def renovacion_adulta(general, c, pregunta):
    """Lista cerrada desde la regla general autorizada, nunca desde el LLM."""
    from app.graph.adult_context import valor
    authorized = 'Corresponde únicamente si el DNI está vencido o le quedan 60 días o menos de vigencia; con más de 60 días no corresponde renovar.'
    if authorized not in general:
        return None
    requested = set(c.get('consulta_renovacion', []))
    eligibility = 'elegibilidad' in requested or consulta_elegibilidad(pregunta)
    requested_question = pregunta
    validity = valor(c, 'vigencia')
    if eligibility and validity in {'', 'vigente'}:
        return ACLARACION_VIGENCIA
    if validity == 'mas_60':
        return ('No, todavía no corresponde renovar su DNI. '
                'El DNI conserva más de 60 días de vigencia. '
                'Podrá renovarlo cuando le queden 60 días o menos, o si ya está vencido.')
    fee = re.search(r'\bTasa (€\d+(?:[.,]\d+)?)\.', general)
    photo = re.search(r'Dos fotografías\. Fotografía obligatoria:.*?(?= Puede solicitar)', general)
    url = re.search(r'https://bookeo\.com/[^\s]+', general)
    if not fee or not photo or not url:
        return None
    topic = c['tema']
    # La consulta puede pedir a la vez importe y documentos; no perder la segunda parte.
    explicit_documents = bool(re.search(r'documentaci[oó]n|documentos|requisit|fotograf|\bfotos?\b|qu[eé] (?:debo )?(?:llevar|presentar)', requested_question, re.I))
    explicit_documents = explicit_documents or bool(requested & {'requisitos', 'fotografias'})
    documents = (topic == 'fotografias' or (topic in {'requisitos', 'otra'} and not eligibility) or explicit_documents)
    parts = []
    if eligibility and validity in {'vencido', 'hasta_60'}:
        parts.append('Sí, puede renovar su DNI ahora. '
                     'La renovación corresponde cuando el DNI está vencido o le quedan 60 días o menos de vigencia.')
    if valor(c, 'vigencia') in {'', 'vigente'}:
        parts.append('La renovación corresponde si el DNI está vencido o le quedan 60 días o menos; '
                     'con más de 60 días de vigencia no corresponde renovarlo.')
    if 'coste' in requested or topic == 'coste' or (topic == 'otra' and not eligibility) or re.search(r'cu[aá]nto cuesta|coste|costo|tasa', requested_question, re.I):
        parts.append('**Tasa de renovación individual:** ' + fee[1] + '.')
    if documents:
        parts.append('**Documentación confirmada para la renovación:**\n\n- ' + photo[0])
        if topic != 'fotografias':
            parts.append('**Cita previa:**\n' + url[0].rstrip('.'))
    if valor(c, 'modificacion') == 'domicilio':
        address = 'Puede solicitar cambio de dirección durante la renovación.'
        if address in general:
            parts.append(address)
    if topic == 'cita' or 'cita' in requested:
        parts.append('**Cita previa:**\n' + url[0].rstrip('.'))
    return '\n\n'.join(parts)


def _datos_civiles_ciudadanos(general):
    """Extraer hechos de la regla autorizada; formato desconocido no se completa."""
    formal = re.search(
        r'Actas de sustento emitidas en Perú: originales, apostilladas por el Ministerio de Relaciones Exteriores '
        r'y con emisión no mayor a (\d+) meses; en buen estado\.', general)
    fee = re.search(r'\bTasa (€\d+(?:[.,]\d+)?)\.', general)
    photo = re.search(r'(Fotografía obligatoria:.*?)(?= La ficha PDF específica no indica cantidad de fotos;)', general)
    url = re.search(r'Cita: (https://bookeo\.com/[^\s]+)', general)
    if not all((formal, fee, photo, url)) or 'No se confirma combinación con renovación ni suma de tasas.' not in general:
        return None
    return {'formalidades': ('con apostilla del Ministerio de Relaciones Exteriores, '
                             'emisión no mayor a ' + formal[1] + ' meses y en buen estado'),
            'tasa': fee[1], 'foto': photo[1], 'cita': url[1].rstrip('.')}


def _apellido_ciudadano(surname, decision, data):
    if decision == 'no':
        return ''
    match = re.fullmatch(
        r'Si desea recuperar el apellido materno tras divorcio o viudez: (acta de nacimiento original)\. '
        r'Si se emitió en Perú, aplicar las condiciones generales de documentos peruanos\.', surname.strip())
    if not match:
        return None
    title = 'Recuperación del apellido materno solicitada' if decision == 'si' else 'Recuperación del apellido materno (solo si la necesita)'
    condition = 'Para recuperar su apellido materno' if decision == 'si' else 'Si desea recuperar su apellido materno'
    return ('**' + title + '**\n\n- ' + condition + ', presente además el ' + match[1] + '.\n'
            '- Si se emitió en Perú: ' + data['formalidades'] + '.')


def _condiciones_ciudadanas(data):
    return ('**Condiciones del trámite**\n\n'
            '- **Tasa individual:** ' + data['tasa'] + '.\n'
            '- **Fotografías obligatorias:** confirme con el Consulado la cantidad que debe llevar.\n\n'
            '<details><summary>Características obligatorias de las fotografías</summary>\n\n'
            + data['foto'] + '\n\n</details>\n\n'
            '- **Cita previa:**\n' + data['cita'] + '\n\n'
            'Si también necesita renovar, confirme con el Consulado si puede realizar ambos trámites juntos '
            'y qué pago corresponde.')


def divorcio_ciudadano(general, principal, surname='', decision=''):
    data = _datos_civiles_ciudadanos(general)
    marriage = re.fullmatch(
        r'De casado a divorciado: (acta de matrimonio peruana original con anotación de disolución del divorcio)\. '
        r'Aplicar condiciones generales de documentos peruanos\.', principal.strip())
    if not data or not marriage:
        return None
    optional = _apellido_ciudadano(surname, decision, data)
    if optional is None:
        return None
    parts = ['**Actualización del estado civil por divorcio**',
             '**Documentación principal:**\n\n- Presente el ' + marriage[1] + '.\n'
             '- Para esta acta peruana: ' + data['formalidades'] + '.',
             optional, _condiciones_ciudadanas(data)]
    return '\n\n'.join(part for part in parts if part)


def viudez_italiana_ciudadana(general, marriage, death, surname='', decision='', pregunta=''):
    data = _datos_civiles_ciudadanos(general)
    italian = re.search(
        r'^Únicamente para cónyuge italiano fallecido en Italia: presentar un '
        r'(acta de defunción plurilingüe emitida por la municipalidad italiana y legalizada por la Prefectura competente)\.', death)
    peru = re.search(r'si está registrado en Perú, (acta de matrimonio peruana original) con las condiciones generales de documentos peruanos;', marriage)
    consular = re.search(r'si está registrado en una oficina consular peruana, (copia certificada emitida por dicha oficina)\.', marriage)
    if (not all((data, italian, peru, consular))
            or 'Este documento sustituye a la certificación consular de defunción.' not in death
            or 'No exigir adicionalmente otra acta de defunción por inferencia.' not in death):
        return None
    optional = _apellido_ciudadano(surname, decision, data)
    if optional is None:
        return None
    funeral = ('**1. Documento de defunción (cónyuge italiano fallecido en Italia)**\n\n'
               '- Para acreditar la defunción, presente únicamente el ' + italian[1] + '.\n'
               '- No necesita presentar una certificación consular de defunción adicional: este acta la sustituye.')
    if re.search(r'(?:por qu[eé]|explique|motivo)[^?!.]{0,160}'
                 r'(?:certificaci[oó]n|registro|registrar|defunci[oó]n)', pregunta, re.I):
        reason = re.search(r'su fallecimiento no se registra como defunción de un ciudadano peruano en el registro consular peruano\.', death)
        if reason:
            funeral += '\n\nEn este caso, ' + reason[0]
    parts = ['**Actualización del estado civil por viudez**', funeral,
             '**2. Documento de matrimonio (según dónde esté registrado)**\n\n'
             '- Si está registrado en Perú: presente el ' + peru[1] + ', ' + data['formalidades'] + '.\n'
             '- Si está registrado en una oficina consular peruana: presente la ' + consular[1] + '.',
             optional, _condiciones_ciudadanas(data)]
    return '\n\n'.join(part for part in parts if part)
