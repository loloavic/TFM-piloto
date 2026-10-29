"""Presentación determinista de textos ya autorizados; sin inferir hechos."""
import re


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
        'La ficha permite cambio de dirección; no detalla documentos adicionales.':
            'Puede solicitar el cambio de dirección. Confirme con el Consulado qué documentación adicional necesita.',
        'La ficha permite cambio de imagen o firma; no detalla otros documentos adicionales.':
            'Puede solicitar el cambio de imagen o firma. Confirme con el Consulado qué documentación adicional necesita.',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def requisitos_viudez(general, marriage, death, surname=''):
    """Conservar las condiciones completas, agrupando los documentos por finalidad."""
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
    parts = ['Para actualizar su DNI por viudez, tenga en cuenta:',
             '- **Defunción:** ' + death.strip(),
             '- **Matrimonio:** ' + marriage.strip()]
    if surname:
        parts.append('- **Recuperación del apellido materno:** ' + texto_ciudadano(surname.strip()))
    parts.extend(['**Condiciones del trámite**\n\n' + general.strip(), details])
    return '\n\n'.join(p for p in parts if p)


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


def consulta_elegibilidad(pregunta):
    """Tema de presentación; no confirma operaciones, edad ni elegibilidad."""
    return bool(re.search(
        r'\b(?:puedo|puede|podr[ií]a|me corresponde|corresponde|se puede|es posible)\b'
        r'[^?!.]{0,90}\brenovar(?:lo|la)?\b', pregunta, re.I))


def renovacion_adulta(general, c, pregunta, historial=()):
    """Lista cerrada desde la regla general autorizada, nunca desde el LLM."""
    from app.graph.adult_context import valor
    authorized = 'Corresponde únicamente si el DNI está vencido o le quedan 60 días o menos de vigencia; con más de 60 días no corresponde renovar.'
    if authorized not in general:
        return None
    eligibility = consulta_elegibilidad(pregunta)
    requested_question = pregunta
    # Una respuesta a nuestra aclaración continúa esa pregunta, sin convertir
    # el historial en fuente de hechos. La decisión usa solo vigencia canónica.
    if (c['tema'] == 'otra' and re.search(r'\b(?:vence|vencera|vencido|vigencia|quedan|faltan)\b', pregunta, re.I)
            and any(turn.get('respuesta') == ACLARACION_VIGENCIA for turn in historial[-2:])):
        eligibility = True
        previous = next(turn for turn in reversed(historial[-2:])
                        if turn.get('respuesta') == ACLARACION_VIGENCIA)
        requested_question = previous.get('pregunta', '') + '\n' + pregunta
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
    documents = (topic == 'fotografias' or (topic in {'requisitos', 'otra'} and not eligibility) or explicit_documents)
    parts = []
    if eligibility and validity in {'vencido', 'hasta_60'}:
        parts.append('Sí, puede renovar su DNI ahora. '
                     'La renovación corresponde cuando el DNI está vencido o le quedan 60 días o menos de vigencia.')
    if valor(c, 'vigencia') in {'', 'vigente'}:
        parts.append('La renovación corresponde si el DNI está vencido o le quedan 60 días o menos; '
                     'con más de 60 días de vigencia no corresponde renovarlo.')
    if topic == 'coste' or (topic == 'otra' and not eligibility) or re.search(r'cu[aá]nto cuesta|coste|costo|tasa', requested_question, re.I):
        parts.append('**Tasa de renovación individual:** ' + fee[1] + '.')
    if documents:
        parts.append('**Documentación confirmada para la renovación:**\n\n- ' + photo[0])
        if topic != 'fotografias':
            parts.append('**Cita previa:**\n' + url[0].rstrip('.'))
    if valor(c, 'modificacion') == 'domicilio':
        address = 'Puede solicitar cambio de dirección durante la renovación.'
        if address in general:
            parts.append(address)
    if topic == 'cita':
        parts.append('**Cita previa:**\n' + url[0].rstrip('.'))
    return '\n\n'.join(parts)
