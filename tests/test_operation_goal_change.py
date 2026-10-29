"""Cambiar de objetivo no significa solicitar una combinación."""
import pytest
from tests.test_adult_dni import motor, snapshot
from app.graph.adult_context import valor


def start(service,days=61):
    first=service.responder(f'Mi DNI vence dentro de {days} días. ¿Puedo renovarlo ahora?')
    service.responder('mayor de edad',first['session_id'],first['session_token'])
    return first['session_id'],first['session_token']


def test_reproduccion_renovacion_no_procede_luego_divorcio(motor):
    service,_,_=motor
    sid,token=start(service)
    before=snapshot(service,sid)['contexto_canonico']
    r=service.responder('pero necesito actualizar mi estado civil a divorciado',sid,token)
    c=snapshot(service,sid)['contexto_canonico']
    assert c['operacion']['valor']=='rectificacion'
    assert valor(c,'modificacion')=='estado_civil' and valor(c,'transicion')=='divorcio'
    assert valor(c,'vigencia')=='mas_60'
    assert c['titular']==before['titular'] and c['edad']==before['edad']
    assert not c['consulta_renovacion']
    assert not c['pendientes']
    assert 'solo si' in r['respuesta'] and {f['archivo'] for f in r['fuentes']}=={'dni_mayor_estado_civil.txt'}


def test_rectificar_fecha_independiente_no_se_suprime(motor):
    service,_,_=motor
    sid,token=start(service)
    r=service.responder('Necesito rectificar mi fecha de nacimiento en el DNI',sid,token)
    assert r['intencion']=='dni_adulto_rectificacion'
    assert {f['archivo'] for f in r['fuentes']}=={'dni_mayor_rectificacion.txt'}
    assert not snapshot(service,sid)['contexto_canonico']['consulta_renovacion']

@pytest.mark.parametrize('recover,rules',[(False,{'general','divorcio'}),
                                       (True,{'general','divorcio','apellido'})])
def test_divorcio_independiente_con_apellido_y_repreguntas(recover,rules,motor):
    service,_,prompts=motor
    sid,token=start(service)
    service.responder('pero necesito actualizar mi estado civil a divorciado',sid,token)
    answer='Quiero recuperar mi apellido materno' if recover else 'No quiero recuperar el apellido materno'
    r=service.responder(answer,sid,token)
    assert r['intencion']=='dni_adulto_rectificacion'
    assert {f['archivo'] for f in r['fuentes']}=={'dni_mayor_estado_civil.txt'}
    assert {f['regla'] for f in r['fuentes']}==rules
    assert 'anotación de disolución del divorcio' in r['respuesta'] and not prompts
    assert ('acta de nacimiento original' in r['respuesta'])==recover
    for q in ['¿Qué documentos debo presentar?', '¿Cuánto cuesta?', '¿Dónde solicito la cita?']:
        r=service.responder(q,sid,token)
        assert r['intencion']=='dni_adulto_rectificacion'
        assert {f['archivo'] for f in r['fuentes']}=={'dni_mayor_estado_civil.txt'}
        assert not r['respuesta'].startswith('No, todavía no corresponde renovar')
    c=snapshot(service,sid)['contexto_canonico']
    assert c['operacion']['valor']=='rectificacion' and valor(c,'vigencia')=='mas_60'


def test_90_dias_luego_casado_pide_solo_lugar_matrimonio(motor):
    service,_,_=motor
    sid,token=start(service,90)
    r=service.responder('Necesito actualizar mi estado civil a casado',sid,token)
    c=snapshot(service,sid)['contexto_canonico']
    assert c['operacion']['valor']=='rectificacion' and valor(c,'transicion')=='matrimonio'
    assert c['pendientes']=={'adulto_matrimonio':'faltante'}
    assert 'Perú o fuera de Perú' in r['respuesta']
    r=service.responder('En Perú',sid,token)
    assert {f['regla'] for f in r['fuentes']}=={'general','matrimonio_peru'}
    r=service.responder('¿Qué documentos de matrimonio debo presentar?',sid,token)
    assert {f['archivo'] for f in r['fuentes']}=={'dni_mayor_estado_civil.txt'}


@pytest.mark.parametrize('query',[
    'Necesito renovar mi DNI y rectificar mi fecha de nacimiento',
    'También necesito rectificar mi fecha de nacimiento',
])
def test_solicitud_conjunta_o_adicional_se_conserva_controlada(query,motor):
    service,_,prompts=motor
    sid,token=start(service,59)
    r=service.responder(query,sid,token)
    c=snapshot(service,sid)['contexto_canonico']
    assert c['operacion']['valor']=='renovacion'
    assert {f['archivo'] for f in r['fuentes']}=={'dni_mayor_renovacion.txt','dni_mayor_rectificacion.txt'}
    assert 'no_acumulacion' in {f['regla'] for f in r['fuentes']}
    assert 'no son acumulables' in r['respuesta'] and not prompts


@pytest.mark.parametrize('reject',[False,True])
def test_vencido_luego_civil_no_crea_combinacion_ni_bloqueo(reject,motor):
    service,_,_=motor
    first=service.responder('Soy adulto y quiero renovar mi DNI vencido')
    sid,token=first['session_id'],first['session_token']
    if reject: service.responder('No quiero renovar',sid,token)
    r=service.responder('Necesito actualizar mi estado civil a divorciado',sid,token)
    c=snapshot(service,sid)['contexto_canonico']
    assert c['operacion']['valor']=='rectificacion'
    assert valor(c,'vigencia')=='vencido'
    assert not c['pendientes']
    r=service.responder('No quiero recuperar el apellido materno',sid,token)
    assert {f['archivo'] for f in r['fuentes']}=={'dni_mayor_estado_civil.txt'}
    assert 'no_acumulacion' not in {f['regla'] for f in r['fuentes']}
    assert ('renovacion' in snapshot(service,sid)['contexto_canonico']['rechazadas'])==reject


def test_civil_luego_pregunta_independiente_de_renovacion(motor):
    service,_,_=motor
    sid,token=start(service)
    service.responder('Necesito actualizar mi estado civil a divorciado',sid,token)
    service.responder('No quiero recuperar el apellido materno',sid,token)
    r=service.responder('¿Puedo renovar mi DNI ahora?',sid,token)
    c=snapshot(service,sid)['contexto_canonico']
    assert c['operacion']['valor']=='renovacion'
    assert valor(c,'vigencia')=='mas_60' and not valor(c,'modificacion')
    assert r['respuesta'].startswith('No, todavía no corresponde renovar')
    assert {f['archivo'] for f in r['fuentes']}=={'dni_mayor_renovacion.txt'}


def test_coste_anterior_no_bloquea_nuevo_objetivo(motor):
    service,_,_=motor
    sid,token=start(service)
    service.responder('¿Cuánto cuesta?',sid,token)
    r=service.responder('pero necesito actualizar mi estado civil a divorciado',sid,token)
    c=snapshot(service,sid)['contexto_canonico']
    assert c['operacion']['valor']=='rectificacion' and not c['pendientes']
    assert {f['archivo'] for f in r['fuentes']} == {'dni_mayor_estado_civil.txt'}
    assert 'solo si' in r['respuesta']


@pytest.mark.parametrize('bad_case',['ausente','obsoleta','incompleta','contradictoria'])
def test_fuente_civil_invalida_no_recicla_fuente_renovacion(bad_case,motor):
    from copy import deepcopy
    service,retrieve,_=motor
    sid,token=start(service)
    service.responder('Necesito actualizar mi estado civil a divorciado',sid,token)
    docs=deepcopy(retrieve.return_value)
    current=next(d for d in docs if d['metadata']['archivo']=='dni_mayor_estado_civil.txt'
                 and d['contenido'].startswith('[[REGLA:divorcio]]'))
    if bad_case=='ausente': docs.remove(current)
    elif bad_case=='incompleta': current['contenido']=current['contenido'].replace('[[FIN]]','')
    elif bad_case=='obsoleta': current['contenido']=current['contenido'].replace('original','fotocopia')
    else: docs.append({**current,'contenido':current['contenido'].replace('original','fotocopia')})
    retrieve.return_value=docs
    r=service.responder('No quiero recuperar el apellido materno',sid,token)
    assert not r['fuentes'] and r['verificacion'].startswith('abstencion_documental')
    assert not r['respuesta'].startswith('No, todavía no corresponde renovar')


def test_otro_titular_y_sesion_no_reutilizan_condiciones_civiles(motor):
    service,_,_=motor
    sid,token=start(service)
    service.responder('Necesito actualizar mi estado civil a divorciado',sid,token)
    r=service.responder('Ahora quiero renovar el DNI de mi hijo menor',sid,token)
    c=snapshot(service,sid)['contexto_canonico']
    assert r['intencion']=='dni_menor_renovacion'
    assert not c['condiciones_adulto'] and not c['consulta_renovacion']
    new=service.responder('Necesito actualizar mi estado civil a divorciado')
    assert new['session_id']!=sid and not new['fuentes']
    assert not snapshot(service,new['session_id'])['contexto_canonico']['edad']['valor']


def test_documento_de_tercero_no_actualiza_estado_civil_del_titular(motor):
    service,_,_=motor
    sid,token=start(service)
    r=service.responder('¿Debo presentar el DNI de mi padre como documento de apoyo?',sid,token)
    c=snapshot(service,sid)['contexto_canonico']
    assert c['operacion']['valor']=='renovacion'
    assert not valor(c,'modificacion')
    assert all(f['archivo']!='dni_mayor_estado_civil.txt' for f in r['fuentes'])


def test_destino_divorciado_no_se_reemplaza_por_matrimonio_historico(motor):
    service,_,_=motor
    sid,token=start(service)
    r=service.responder('Necesito actualizar mi estado civil a divorciado. Me casé en Perú.',sid,token)
    c=snapshot(service,sid)['contexto_canonico']
    assert valor(c,'transicion')=='divorcio'
    assert not c['pendientes']
    assert 'apellido materno' in r['respuesta']


def test_destinos_contradictorios_no_se_resuelven_por_arrastre(motor):
    service,_,_=motor
    sid,token=start(service)
    r=service.responder('Necesito actualizar mi estado civil a casado y a divorciado',sid,token)
    c=snapshot(service,sid)['contexto_canonico']
    assert c['pendientes']['adulto_transicion']=='contradiccion'
    assert not r['fuentes'] and not valor(c,'transicion')


def test_solicitud_conjunta_civil_sigue_sin_autorizacion_documental(motor):
    service,_,_=motor
    sid,token=start(service,59)
    r=service.responder('Necesito renovar mi DNI y actualizar mi estado civil a divorciado',sid,token)
    c=snapshot(service,sid)['contexto_canonico']
    assert c['operacion']['valor']=='renovacion' and valor(c,'modificacion')=='estado_civil'
    assert not r['fuentes'] and 'no está confirmada' in r['respuesta']
    assert r['verificacion'].startswith('abstencion_documental')


def test_nuevo_objetivo_no_retoma_coste_de_aclaracion_anterior(motor):
    service,_,_=motor
    first=service.responder('Soy adulto y quiero renovar mi DNI y rectificar mis nombres. ¿Cuánto cuesta?')
    sid,token=first['session_id'],first['session_token']
    assert snapshot(service,sid)['contexto_canonico']['pendientes']=={'adulto_vigencia':'faltante'}
    r=service.responder('pero necesito actualizar mi estado civil a divorciado',sid,token)
    c=snapshot(service,sid)['contexto_canonico']
    assert c['operacion']['valor']=='rectificacion'
    assert not c['pendientes']
    assert not c['consulta_pendiente'] and c['tema']=='otra'
    assert 'solo si' in r['respuesta'] and {f['archivo'] for f in r['fuentes']}=={'dni_mayor_estado_civil.txt'}
