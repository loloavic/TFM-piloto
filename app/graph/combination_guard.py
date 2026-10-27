"""Salida cerrada para combinaciones: citas individuales, nunca síntesis normativa LLM."""
import re

from app.graph.adult_context import ADULT_FILES, REGLAS_COMUNES, plan, valor
from app.graph.context_policy import ruta_documental

COMMON_CONFLICT = 'Las disposiciones comunes recuperadas no coinciden; no puedo confirmar su alcance.'

UNSUPPORTED = (
    'La combinación solicitada no está confirmada en las fichas aportadas. '
    'No puedo proporcionar requisitos combinados ni sumar tasas. '
    'En rectificación de datos con renovación, indique si el DNI está vencido; '
    'la combinación con cambio de estado civil requiere confirmación del Consulado.'
)
MISSING = (
    'No cuento con información documental suficiente para responder con seguridad. '
    'Faltan reglas o fuentes necesarias; no puedo confirmar condiciones combinadas.'
)
LIMIT = (
    'Las condiciones individuales no permiten confirmar una lista combinada definitiva, '
    'acumular requisitos, trasladar cantidades de fotografías ni establecer '
    'un importe total, una tasa única o una exoneración. Confirme el alcance combinado con el Consulado.'
)


def respuesta_controlada(state):
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
    if len(required) == 1 and not common and not italian_widow:
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

    if italian_widow:
        file = 'dni_mayor_estado_civil.txt'
        # Excluir únicamente la reserva de defunción de otras nacionalidades.
        marriage, separator, _ = rules[(file, 'viudez_italia')].partition(' Para cónyuge italiano aplicar')
        if not separator:
            return MISSING  # Versión incompatible: no emitir una reserva antigua.
        paragraphs = [rules[(file, 'general')], marriage, rules[(file, 'italiano')]]
        if (file, 'apellido') in rules:
            paragraphs.append(rules[(file, 'apellido')])
        return '\n\n'.join(paragraphs)

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
    topic = c['tema']
    if topic == 'coste':
        fees = [re.search(r'\bTasa (€\d+(?:[.,]\d+)?)\.', text) for text in (rect, renew)]
        if not all(fees):
            return 'Las fuentes recuperadas no permiten verificar las tasas individuales. ' + LIMIT
        return (f'La ficha de rectificación indica {fees[0][1]} y la de renovación {fees[1][1]}, '
                'cada una para su procedimiento individual. '
                'No documentan un importe total ni si las tasas se acumulan para este supuesto. ' + LIMIT)
    if topic == 'fotografias':
        # Citar el párrafo original, conservando explícitamente su ámbito.
        excerpts = []
        for label, text in [('Rectificación individual', rect), ('Renovación individual', renew)]:
            match = re.search(r'(?:Dos fotografías\. )?Fotografía obligatoria:.*?(?= Cita:| Puede solicitar|$)', text)
            if not match:
                return 'No puedo verificar las condiciones fotográficas individuales. ' + LIMIT
            excerpts.append(label + ' — cita de su ficha: «' + match[0].strip() + '»')
        return 'No se confirma una cantidad de fotografías para el supuesto combinado.\n\n' + '\n\n'.join(excerpts) + '\n\n' + LIMIT
    if topic in {'requisitos', 'otra'}:
        specific = [(file, rule, text) for (file, rule), text in rules.items() if rule != 'general']
        paragraphs = ['Información documentada para cada procedimiento individual; no es una lista combinada definitiva.']
        for file, rule, text in sorted(specific):
            paragraphs.append(f'Ficha de rectificación ({file}, regla {rule}) — cita: «{text.strip()}»')
        if not specific:
            paragraphs.append('No se han recuperado reglas específicas de documentación adicional para este caso.')
        paragraphs.append('La ficha de rectificación vincula el DNI vencido a renovación, pero no concreta cómo se integran ambas listas de requisitos.')
        paragraphs.append(LIMIT)
        return '\n\n'.join(paragraphs)
    if topic == 'plazo':
        return 'No puedo confirmar un plazo para la combinación a partir de estas fichas. ' + LIMIT
    if topic == 'cita':
        # Una URL común no demuestra autorización para gestionar una cita conjunta.
        urls = [re.findall(r'https://bookeo\.com/[^\s]+', text) for text in (rect, renew)]
        common = set(urls[0]) & set(urls[1])
        if len(common) != 1:
            return 'No puedo verificar un enlace común de reserva en las fuentes recuperadas. ' + LIMIT
        return ('Ambas fichas individuales indican este enlace: ' + common.pop().rstrip('.') +
                '\nNo puedo confirmar que una sola reserva cubra ambos procedimientos. ' + LIMIT)
    return 'No puedo confirmar condiciones conjuntas para esa consulta. ' + LIMIT
