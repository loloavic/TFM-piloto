"""Salida cerrada para combinaciones: citas individuales, nunca síntesis normativa LLM."""
import re

from app.graph.adult_context import ADULT_FILES, REGLAS_COMUNES, plan, valor
from app.graph.context_policy import ruta_documental
from app.graph.presentation import texto_ciudadano, requisitos_viudez, incertidumbre_viudez, renovacion_adulta, requisitos_civiles, divorcio_ciudadano, viudez_italiana_ciudadana

COMMON_CONFLICT = 'No puedo confirmar esta información porque hay versiones incompatibles. Consulte con el Consulado antes de acudir.'

UNSUPPORTED = (
    'La combinación solicitada no está confirmada. '
    'Consulte con el Consulado si puede realizar ambos trámites y qué debe pagar. '
    'No puedo proporcionar requisitos combinados ni sumar tasas.'
)
MISSING = (
    'No cuento con información documental suficiente para responder con seguridad. '
    'Consulte con el Consulado antes de acudir; no puedo confirmar las condiciones de su consulta.'
)
LIMIT = (
    'Confirme con el Consulado los requisitos y el pago para los trámites combinados. '
    'No puedo confirmar una lista conjunta, sumar requisitos o fotografías, '
    'ni establecer un importe total, una tasa única o una exoneración.'
)


def respuesta_controlada(state):
    result = _respuesta_controlada(state)
    return texto_ciudadano(result) if result is not None else None


def _respuesta_controlada(state):
    """Recalcular desde contexto validado y reglas recuperadas, sin confiar en el borrador.

    None significa ámbito ajeno al control; no certifica su fundamentación.
    La completitud se valida también aquí, independientemente del nodo RAG.
    """
    c = state.get('contexto_canonico')
    intent = state.get('intencion')
    if intent not in ADULT_FILES or ruta_documental(c) != intent:
        return None
    required = plan(c)
    if not required:
        return UNSUPPORTED
    common = c['tema'] in REGLAS_COMUNES and all(ids == {c['tema']} for ids in required.values())
    italian_widow = (valor(c, 'modificacion') == 'estado_civil'
                     and valor(c, 'transicion') == 'viudez'
                     and valor(c, 'defuncion') == 'italia'
                     and valor(c, 'italiano') == 'si'
                     and c['tema'] in {'otra', 'requisitos'})
    uncertain_widow = (valor(c, 'modificacion') == 'estado_civil'
                       and valor(c, 'transicion') == 'viudez'
                       and c['tema'] in {'otra', 'requisitos'}
                       and any('OBSERVACIÓN PENDIENTE' in f.get('contenido', '')
                               for f in state.get('fragmentos', [])))
    civil_requirements = (valor(c, 'modificacion') == 'estado_civil'
                          and valor(c, 'transicion') in {'divorcio', 'viudez'}
                          and c['tema'] in {'otra', 'requisitos'})
    ordinary_renewal = (intent == 'dni_adulto_renovacion'
                        and required == {'dni_mayor_renovacion.txt': {'general'}})
    if len(required) == 1 and not common and not italian_widow and not uncertain_widow and not ordinary_renewal and not civil_requirements:
        return None
    rules = {}
    for f in state.get('fragmentos', []):
        meta = f.get('metadata', {})
        key = (meta.get('archivo'), meta.get('regla'))
        if key[0] not in required or key[1] not in required[key[0]]:
            return MISSING
        if key in rules and rules[key] != f.get('contenido'):
            return MISSING
        rules[key] = f.get('contenido', '')
    expected = {(file, rule) for file, ids in required.items() for rule in ids}
    if set(rules) != expected or not all(rules.values()):
        return MISSING

    if ordinary_renewal:
        response = renovacion_adulta(rules[('dni_mayor_renovacion.txt', 'general')], c, state.get('pregunta', ''))
        return response if response is not None else MISSING

    if italian_widow:
        file = 'dni_mayor_estado_civil.txt'
        # Excluir únicamente la reserva de defunción de otras nacionalidades.
        marriage, separator, _ = rules[(file, 'viudez_italia')].partition(' Para cónyuge italiano aplicar')
        if not separator:
            return MISSING  # Versión incompatible: no emitir una reserva antigua.
        response = viudez_italiana_ciudadana(rules[(file, 'general')], marriage, rules[(file, 'italiano')],
                                               rules.get((file, 'apellido'), ''), valor(c, 'apellido'), state.get('pregunta', ''))
        return response if response is not None else MISSING

    if uncertain_widow:
        file = 'dni_mayor_estado_civil.txt'
        marriage = rules.get((file, 'viudez_italia'), '').partition(' Para cónyuge italiano aplicar')[0]
        if not marriage:
            marriage = 'Confirme con el Consulado cómo acreditar el matrimonio en su situación.'
        return requisitos_viudez(rules[(file, 'general')], marriage,
                                 incertidumbre_viudez(state), rules.get((file, 'apellido'), ''), valor(c, 'apellido'))

    if civil_requirements:
        file = 'dni_mayor_estado_civil.txt'
        transition = valor(c, 'transicion')
        rule = 'divorcio' if transition == 'divorcio' else 'viudez_' + valor(c, 'defuncion')
        main = rules.get((file, rule))
        if not main:
            return MISSING
        if transition == 'divorcio':
            response = divorcio_ciudadano(rules[(file, 'general')], main,
                                          rules.get((file, 'apellido'), ''), valor(c, 'apellido'))
            return response if response is not None else MISSING
        return requisitos_civiles(rules[(file, 'general')],
                                  '**Documentación principal:**\n\n' + texto_ciudadano(main),
                                  rules.get((file, 'apellido'), ''), valor(c, 'apellido'), transition)

    if common:
        contents = {text.strip() for text in rules.values()}
        if len(contents) != 1:
            return COMMON_CONFLICT
        return contents.pop()

    rect = rules.get(('dni_mayor_rectificacion.txt', 'general'), '')
    renew = rules.get(('dni_mayor_renovacion.txt', 'general'), '')
    # Las únicas combinaciones autorizadas hoy contienen estas dos fichas.
    if not rect or not renew:
        return MISSING
    tariff = rules.get(('dni_mayor_renovacion.txt', 'no_acumulacion'), '')
    if 'no son acumulables cuando ambas operaciones se realizan conjuntamente' not in tariff:
        return MISSING
    # La política tarifaria es evidencia obligatoria, no una inferencia de €7 + €7.
    limit = LIMIT + '\n\n' + tariff.strip()
    topic = c['tema']
    if topic == 'coste':
        fees = [re.search(r'\bTasa (€\d+(?:[.,]\d+)?)\.', text) for text in (rect, renew)]
        if not all(fees):
            return 'Las fuentes recuperadas no permiten verificar las tasas individuales. ' + limit
        specific = [texto_ciudadano(text.strip()) for (file, rule), text in rules.items() if file == 'dni_mayor_rectificacion.txt' and rule != 'general']
        docs = ('\n\n**Para rectificar los datos:**\n\n' + '\n\n'.join(specific)) if re.search(r'document|requisit', state.get('pregunta', ''), re.I) else ''
        return ('Por la vigencia indicada corresponde renovar y puede incorporar la rectificación solicitada. '
                f'La rectificación cuesta {fees[0][1]} y la renovación {fees[1][1]}, '
                'cada una para su procedimiento individual. '
                'No puedo confirmar el importe total del caso conjunto. ' + limit + docs)
    if topic == 'fotografias':
        # Citar el párrafo original, conservando explícitamente su ámbito.
        excerpts = []
        for label, text in [('Rectificación individual', rect), ('Renovación individual', renew)]:
            match = re.search(r'(?:Dos fotografías\. )?Fotografía obligatoria:.*?(?= Cita:| Puede solicitar|$)', text)
            if not match:
                return 'No puedo verificar las condiciones fotográficas individuales. ' + limit
            excerpts.append(label + ' — ' + texto_ciudadano(match[0].strip()))
        return 'No se confirma una cantidad de fotografías para el supuesto combinado.\n\n' + '\n\n'.join(excerpts) + '\n\n' + limit
    if topic in {'requisitos', 'otra'}:
        specific = [(file, rule, text) for (file, rule), text in rules.items() if file == 'dni_mayor_rectificacion.txt' and rule != 'general']
        paragraphs = ['Información documentada para cada procedimiento individual; no es una lista combinada definitiva.']
        for file, rule, text in sorted(specific):
            paragraphs.append('**Rectificación — documentación individual:**\n\n' + texto_ciudadano(text.strip()))
        if not specific:
            paragraphs.append('No puedo confirmar la documentación adicional que necesita en este caso.')
        paragraphs.append('Por la vigencia indicada corresponde renovar el DNI y puede incorporar la rectificación solicitada. Confirme con el Consulado cómo presentar la documentación y cuál es el importe aplicable; las tasas conjuntas no son acumulables.')
        paragraphs.append(limit)
        return '\n\n'.join(paragraphs)
    if topic == 'plazo':
        return 'No puedo confirmar un plazo para la combinación a partir de estas fichas. ' + limit
    if topic == 'cita':
        # Una URL común no demuestra autorización para gestionar una cita conjunta.
        urls = [re.findall(r'https://bookeo\.com/[^\s]+', text) for text in (rect, renew)]
        common = set(urls[0]) & set(urls[1])
        if len(common) != 1:
            return 'No puedo verificar un enlace común de reserva en las fuentes recuperadas. ' + limit
        return ('Puede consultar las citas de cada trámite aquí: ' + common.pop().rstrip('.') +
                '\nNo puedo confirmar que una sola reserva cubra ambos procedimientos. ' + limit)
    return 'No puedo confirmar condiciones conjuntas para esa consulta. ' + limit
