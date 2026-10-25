"""Fixtures 2.3 escritos explícitamente en V2.2E; sin conversiones de 2.2."""
VERSION='2.3-candidata-1'
META=dict(turno=1,revision=0)


def fact(value,act='observacion',origin='explicito_turno',subject='objetivo'):
    return dict(estado='determinado',valor=value,acto=act,origen=origin,sujeto=subject)


def uncertain(state='incierto',subject='objetivo'):
    return dict(estado=state,valor=None,acto='observacion',origen='explicito_turno',sujeto=subject)


def support(origin='explicito_turno',subject='objetivo'):
    return dict(origen=origin,sujeto=subject)


def operation(op='renovacion',act='solicitud',**kwargs):
    return {op:{act:support(**kwargs)}}


def p(**kwargs):return dict(version=VERSION,**kwargs)


def objective(kind='explicito_unico',ref='ninguno'):
    return dict(identificacion=kind,referente=ref)


def clear(op='renovacion',age='menor',relation='descendiente',ref='ninguno'):
    return p(objetivo=objective(ref=ref),ambito=fact('dni'),relacion=fact(relation),
             edad=fact(age),tema=fact('requisitos','solicitud_afirmativa'),operaciones=operation(op))


# Los 29 turnos siguen la matriz original; solo categorías, sin mensajes.
CASES={
 'E01':(clear(),p(objetivo=objective('referencia_contextual','actual'),tema=fact('coste','solicitud_afirmativa'))),
 'E02':(clear('primera_vez'),p(objetivo=objective('referencia_contextual','actual'),tema=fact('cita','solicitud_afirmativa'))),
 'E03':(p(ambito=fact('dni'),tema=fact('seguimiento','solicitud_afirmativa')),),
 'E04':(clear(),clear(age='adulto',relation='ascendiente',ref='otro')),
 'E05':(clear(),p(operaciones=operation(act='negacion')),
        p(objetivo=objective(ref='actual'),relacion=fact('descendiente','aclaracion')),clear()),
 'E06':(dict(clear('primera_vez'),dni_previo=fact('no')),
        p(objetivo=objective('referencia_contextual','actual'),dni_previo=fact('si','aclaracion'),operaciones=operation())),
 'E07':(clear(),p(edad=fact('adulto')),p(objetivo=objective(ref='actual'),relacion=fact('descendiente','aclaracion')),
        p(edad=fact('menor','aclaracion'))),
 'E08':(dict(clear('primera_vez'),dni_previo=fact('no')),p(operaciones=operation()),p(dni_previo=fact('si','aclaracion'))),
 'E09':(clear(),p(funcion_documento=fact('apoyo'),edad=fact('adulto',subject='acompanante'),
                 tema=fact('requisitos','solicitud_afirmativa'))),
 'E10':(clear(),p(objetivo=objective('multiple')),p(objetivo=objective('ambiguo'))),
 'E11':(clear(age='adulto',relation='propio'),),
 'E12':(clear('duplicado'),),
 'E13':(p(ambito=fact('fuera_alcance')),),
 'E14':(dict(clear(),edad=uncertain()),),
}
