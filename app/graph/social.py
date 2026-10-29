"""Interacciones de cortesía sin inferir hechos ni modificar el contexto DNI."""
import re
import unicodedata


def normalizar(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', texto.lower())
                   if unicodedata.category(c) != 'Mn').strip(' ¿?¡!.,;:')


SALUDO = r'(buenos dias|buenas tardes|buenas noches|hola|buenas)(?: de nuevo)?'


def saludo(texto):
    match = re.match(SALUDO + r'(?=$|[\s,!.?¿¡])', normalizar(texto))
    return ('Buenos días' if match.group(1) == 'buenos dias' else match.group(1).capitalize()) if match else ''


def respuesta_social(texto):
    """Coincidencia completa: cualquier contenido material residual sigue al clasificador."""
    t = normalizar(texto)
    match = re.match(SALUDO + r'(?=$|[\s,!.?¿¡])', t)
    greeting = saludo(texto)
    if match:
        t = t[match.end():].strip(' ¿?¡!.,;:')
    if not t and greeting:
        return (f'¡{greeting}! Soy el asistente virtual de orientación sobre trámites de DNI '
                'del Consulado General del Perú en Turín. ¿En qué puedo ayudarle?')
    if re.fullmatch(r'(?:muchas )?gracias(?: por (?:la informacion|su ayuda|la ayuda|todo))?', t):
        return 'Con gusto. Si necesita alguna otra orientación sobre trámites de DNI, puede consultarme.'
    if re.fullmatch(r'hasta luego|adios|hasta pronto|nos vemos', t):
        return '¡Hasta luego! Si necesita orientación sobre trámites de DNI, puede volver a consultarme.'
    # Pregunta de capacidad, no de requisitos de un procedimiento concreto.
    if re.fullmatch(
        r'(?:puedo (?:hacer (?:(?:aqui|aca) )?consultas|consultar)|'
        r'(?:aqui|aca) puedo consultar) '
        r'(?:sobre|respecto a|acerca de) (?:los )?tramites de dni'
        r'(?: en el consulado(?: general)? de(?:l)? peru(?: en turin)?)?', t):
        prefix = f'¡{greeting}! ' if greeting else ''
        return (prefix + 'Sí, puede consultar información sobre los trámites de DNI disponibles, '
                'sus requisitos, citas y seguimiento. Ofrezco orientación; no realizo trámites, '
                'no emito documentos ni reservo citas por usted. ¿Qué desea consultar?')
    return None
