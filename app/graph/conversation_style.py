"""Formulación acotada: no selecciona rutas ni modifica el contexto canónico."""
import re

from app.graph.classification import normalizar


def menciona_domicilio(pregunta: str) -> bool:
    return bool(re.search(r'\b(?:actualizar|cambiar|cambio|actualizacion)\b.{0,35}\bdomicilio\b', normalizar(pregunta)))


def formular_aclaracion(state: dict, pregunta_base: str) -> str:
    if state.get('motivo_aclaracion') == 'adulto_transicion':
        return ('Con gusto puedo orientarle sobre la actualización de su estado civil en el DNI.\n\n'
                '¿Qué cambio necesita realizar: de soltero a casado, de casado a divorciado o de casado a viudo?')
    issue = tipo_incidencia(state['pregunta'])
    if issue:
        acknowledgment = {
            'disponibilidad': 'Entiendo que no aparecen citas disponibles. ',
            'urgencia': 'Entiendo que necesita una cita pronto. ',
            'acceso': 'Entiendo la dificultad para abrir el enlace. ',
            'error': 'Entiendo que la página de reservas muestra un error. ',
        }[issue]
        return acknowledgment + 'Para poder orientarle, ' + pregunta_base
    if not menciona_domicilio(state['pregunta']):
        return 'Para poder orientarle, ' + pregunta_base
    holder = state.get('contexto_solicitante', {}).get('destinatario')
    target = ' de su hijo' if holder == 'descendiente' else ' del titular'
    acknowledgment = f'Entiendo que necesita actualizar el domicilio del DNI{target}. '
    if state.get('motivo_aclaracion') == 'operacion':
        return (acknowledgment + 'No puedo confirmar que ese cambio corresponda a una renovación con la información disponible. '
                'Para poder orientarle: ¿Desea orientación sobre una renovación o sobre el primer DNI?')
    return acknowledgment + 'Para poder orientarle, ' + pregunta_base


def tipo_incidencia(pregunta: str) -> str:
    text = normalizar(pregunta)
    if re.search(r'\b(?:no aparecen|no hay|sin)\s+(?:citas|disponibilidad|fechas)', text):
        return 'disponibilidad'
    if re.search(r'\bcita\b.*(?:lo antes posible|urgente)|\bnecesito una cita pronto\b', text):
        return 'urgencia'
    if re.search(r'\b(?:enlace|link)\b.*\bno funciona\b', text):
        return 'acceso'
    if re.search(r'\b(?:pagina|reservas|bookeo)\b.*\berror\b', text):
        return 'error'
    return ''


def respuesta_contextual(state: dict) -> str | None:
    """Solo se llama después de autorización y recuperación de fuentes propias.

    No diagnosticar disponibilidad, causas o plazos operativos no documentados.
    Las indicaciones de reintento son orientación de uso, no una regla consular.
    """
    issue = tipo_incidencia(state['pregunta'])
    replies = {
        'disponibilidad': ('Entiendo que no aparecen citas disponibles. No puedo confirmar cuándo se habilitarán nuevas plazas. '
                           'Puede volver a consultar el sistema oficial de reservas del trámite; no puedo confirmar fechas ni reservar por usted.'),
        'urgencia': ('Entiendo que necesita una cita pronto. Consulte las fechas que muestre el sistema oficial de reservas del trámite. '
                     'No puedo garantizar una cita anticipada ni confirmar plazas disponibles.'),
        'acceso': ('Entiendo que no puede abrir el enlace de citas. Con la información disponible no puedo determinar la causa '
                   'ni comprobar si el servicio está funcionando. Puede volver a intentar acceder al sistema oficial de reservas; '
                   'no dispongo de una vía alternativa documentada.'),
        'error': ('Entiendo que la página de reservas muestra un error. No puedo determinar si se debe a falta de citas o a otro motivo. '
                  'Puede volver a consultar el sistema oficial; no dispongo de una explicación documentada del error ni de fechas de apertura.'),
    }
    if issue:
        return replies[issue]
    if menciona_domicilio(state['pregunta']) and 'domicilio' not in normalizar(state.get('contexto', '')):
        return ('Entiendo que desea actualizar el domicilio. La documentación disponible para este trámite no especifica '
                'cómo realizar ese cambio; no puedo confirmar sus requisitos ni equipararlo automáticamente a una renovación.')
    return None
