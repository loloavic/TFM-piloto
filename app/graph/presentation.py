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


def renovacion_adulta(general, c, pregunta):
    """Lista cerrada desde la regla general autorizada, nunca desde el LLM."""
    from app.graph.adult_context import valor
    authorized = 'Corresponde únicamente si el DNI está vencido o le quedan 60 días o menos de vigencia; con más de 60 días no corresponde renovar.'
    if authorized not in general:
        return None
    if valor(c, 'vigencia') == 'mas_60':
        return ('Con más de 60 días de vigencia, no corresponde renovar el DNI. '
                'La renovación corresponde si está vencido o le quedan 60 días o menos. '
                'Si desea rectificar datos, puede consultar ese trámite sin asumir una renovación.')
    fee = re.search(r'\bTasa (€\d+(?:[.,]\d+)?)\.', general)
    photo = re.search(r'Dos fotografías\. Fotografía obligatoria:.*?(?= Puede solicitar)', general)
    url = re.search(r'https://bookeo\.com/[^\s]+', general)
    if not fee or not photo or not url:
        return None
    topic = c['tema']
    # La consulta puede pedir a la vez importe y documentos; no perder la segunda parte.
    documents = topic in {'requisitos', 'otra', 'fotografias'} or bool(re.search(r'document|requisit|fotograf|\bfotos?\b', pregunta, re.I))
    parts = []
    if valor(c, 'vigencia') in {'', 'vigente'}:
        parts.append('La renovación corresponde si el DNI está vencido o le quedan 60 días o menos; '
                     'con más de 60 días de vigencia no corresponde renovarlo.')
    if topic == 'coste' or topic == 'otra' or re.search(r'cu[aá]nto cuesta|coste|costo|tasa', pregunta, re.I):
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
