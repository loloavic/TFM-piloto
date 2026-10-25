"""Matriz fija sintética. Textos de ensayo, nunca datos de ciudadanos reales.

Las salidas simuladas son fixtures de ingeniería, NO predicciones de un LLM.
"""
from dataclasses import dataclass


def atom(dimension, valor, acto='observacion', origen='explicito_turno', sujeto='objetivo'):
    return dict(dimension=dimension, valor=valor, acto=acto, origen=origen, sujeto=sujeto)


def packet(*atoms, faltantes=(), contradicciones=()):
    return dict(version='2.1', evidencias=list(atoms), faltantes=list(faltantes),
                contradicciones=list(contradicciones))


def request(op='renovacion', age='menor', holder='descendiente'):
    return [atom('ambito', 'dni'), atom('titular', holder, 'solicitud_afirmativa'),
            atom('edad', age), atom('operacion', op, 'solicitud_afirmativa'),
            atom('tema', 'requisitos', 'solicitud_afirmativa')]


@dataclass(frozen=True)
class TurnoEvaluacion:
    mensaje: str
    salida_simulada: dict
    # Átomos críticos esperados: subconjunto semántico, independiente del JSON válido.
    evidencias_esperadas: tuple[dict, ...]
    ruta_esperada: str
    decision_esperada: str
    # Valores canónicos críticos, incluso si una ruta equivocada sigue bloqueada.
    canonico_esperado: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Escenario:
    codigo: str
    categoria: str
    turnos: tuple[TurnoEvaluacion, ...]


def turn(message, atoms, route='', decision='aclaracion', *, expected=None, canonical=(), **kwargs):
    return TurnoEvaluacion(message, packet(*atoms, **kwargs),
                           tuple(atoms if expected is None else expected), route, decision, canonical)


REN = 'dni_menor_renovacion'
PRI = 'dni_menor_primera_vez'


def initial(op='renovacion'):
    return turn('¿Qué requisitos necesito para ' +
                ('renovar' if op == 'renovacion' else 'sacar por primera vez') +
                ' el DNI de mi hijo menor de edad?', request(op),
                REN if op == 'renovacion' else PRI, 'documentada',
                expected=[atom('operacion', op, 'solicitud_afirmativa'), atom('edad', 'menor')],
                canonical=(('edad', 'menor'), ('operacion', op)))


ESCENARIOS = (
    Escenario('E01', 'renovacion_coste', (initial(),
        turn('¿Cuánto cuesta?', [atom('tema', 'coste', 'solicitud_afirmativa')],
             REN, 'documentada', canonical=(('operacion', 'renovacion'),)))),
    Escenario('E02', 'primera_inscripcion_cita', (initial('primera_vez'),
        turn('¿Cómo pido la cita?', [atom('tema', 'cita', 'solicitud_afirmativa')],
             PRI, 'documentada', canonical=(('operacion', 'primera_vez'),)))),
    Escenario('E03', 'seguimiento', (
        turn('Quiero consultar el estado de mi trámite de DNI.',
             [atom('ambito', 'dni'), atom('tema', 'seguimiento', 'solicitud_afirmativa')],
             'dni_consulta_estado', 'documentada'),)),
    Escenario('E04', 'cambio_titular', (initial(),
        turn('Ahora es para mi padre adulto. Quiero renovar su DNI.',
             request(age='adulto', holder='adulto') +
             [atom('referencia_titular', 'otro', 'solicitud_afirmativa')],
             decision='abstencion', expected=[atom('referencia_titular', 'otro', 'solicitud_afirmativa'),
                                              atom('edad', 'adulto')],
             canonical=(('titular', 'adulto'), ('edad', 'adulto'))))),
    Escenario('E05', 'negacion_rehabilitacion', (initial(),
        turn('No quiero renovar el DNI.', [atom('operacion', 'renovacion', 'negacion')]),
        turn('Es para mi hijo.', [atom('titular', 'descendiente', 'aclaracion')]),
        turn('Quiero renovar el DNI de mi hijo menor de edad.', request(), REN, 'documentada',
             expected=[atom('operacion', 'renovacion', 'solicitud_afirmativa')]))),
    Escenario('E06', 'correccion', (
        turn('Mi hijo menor nunca tuvo DNI. Quiero sacarlo por primera vez.',
             request('primera_vez') + [atom('dni_previo', 'no')], PRI, 'documentada',
             expected=[atom('dni_previo', 'no'), atom('operacion', 'primera_vez', 'solicitud_afirmativa')]),
        turn('Me equivoqué: ya tuvo DNI. Quiero renovar el DNI del mismo menor.',
             [atom('dni_previo', 'si', 'aclaracion'), atom('operacion', 'renovacion', 'solicitud_afirmativa')],
             REN, 'documentada', canonical=(('dni_previo', 'si'), ('operacion', 'renovacion'))))),
    Escenario('E07', 'contradiccion_edad', (initial(),
        turn('Mi hijo es adulto.', [atom('edad', 'adulto')]),
        turn('Es para mi hijo.', [atom('titular', 'descendiente', 'aclaracion')]),
        turn('Me equivoqué: es menor de edad.', [atom('edad', 'menor', 'aclaracion')],
             REN, 'documentada', canonical=(('edad', 'menor'),)))),
    Escenario('E08', 'contradiccion_dni_previo', (
        turn('Mi hijo menor nunca tuvo DNI. Quiero sacarlo por primera vez.',
             request('primera_vez') + [atom('dni_previo', 'no')], PRI, 'documentada',
             expected=[atom('dni_previo', 'no')]),
        turn('Quiero renovar su DNI.', [atom('operacion', 'renovacion', 'solicitud_afirmativa')]),
        turn('Rectifico: ya tuvo DNI.', [atom('dni_previo', 'si', 'aclaracion')], REN, 'documentada',
             canonical=(('dni_previo', 'si'),)))),
    Escenario('E09', 'documento_acompanante', (initial(),
        turn('¿Debo llevar el DNI de su madre como documento de apoyo?',
             [atom('funcion_documento', 'apoyo'), atom('tema', 'requisitos', 'solicitud_afirmativa')],
             REN, 'documentada', expected=[atom('funcion_documento', 'apoyo')],
             canonical=(('edad', 'menor'), ('titular', 'descendiente'), ('funcion_documento', 'apoyo'))))),
    Escenario('E10', 'referencias_ambiguas', (initial(),
        turn('Es para mi hijo y para mi hija. ¿Qué requisitos necesita?',
             [atom('referencia_titular', 'varios')], contradicciones=['titular']),
        turn('¿Y para él?', [atom('referencia_titular', 'ambigua')], contradicciones=['titular']))),
    Escenario('E11', 'adulto_sin_corpus', (
        turn('Soy adulto y quiero renovar mi DNI.', request(age='adulto', holder='propio'),
             decision='abstencion', expected=[atom('edad', 'adulto'),
                                               atom('operacion', 'renovacion', 'solicitud_afirmativa')],
             canonical=(('edad', 'adulto'), ('operacion', 'renovacion'))),)),
    Escenario('E12', 'duplicado_sin_corpus', (
        turn('Quiero un duplicado del DNI de mi hijo menor de edad.', request('duplicado'),
             decision='abstencion', expected=[atom('operacion', 'duplicado', 'solicitud_afirmativa')],
             canonical=(('operacion', 'duplicado'),)),)),
    Escenario('E13', 'fuera_alcance', (
        turn('Quiero renovar mi pasaporte.', [atom('ambito', 'fuera_alcance')],
             decision='abstencion', canonical=(('ambito', 'fuera_alcance'),)),)),
    Escenario('E14', 'edad_no_concluyente', (
        turn('Quiero renovar el DNI de mi hijo, que es menor de 25 años.',
             [a for a in request() if a['dimension'] != 'edad'] + [atom('edad', 'desconocido')],
             expected=[atom('edad', 'desconocido')], contradicciones=['edad']),)),
)
