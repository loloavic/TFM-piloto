"""Apellido desconocido no bloquea requisitos principales ni se vuelve obligatorio."""
import pytest
from tests.test_adult_dni import motor, snapshot
from app.graph.adult_context import valor

DIVORCE='Soy mayor de edad y necesito actualizar mi estado civil de casado a divorciado en mi DNI. ¿Qué documentos debo presentar?'
WIDOW='Soy mayor de edad y necesito actualizar mi estado civil de casada a viuda en mi DNI. Mi esposo era italiano y falleció en Italia. ¿Qué documentos debo presentar?'

@pytest.mark.parametrize('query,main',[(DIVORCE,'divorcio'),(WIDOW,'italiano')])
def test_documentacion_principal_sin_aclaracion_de_apellido(query,main,motor):
    service,_,prompts=motor
    r=service.responder(query)
    c=snapshot(service,r['session_id'])['contexto_canonico']
    assert r['intencion']=='dni_adulto_rectificacion'
    assert not c['pendientes'] and not valor(c,'apellido')
    assert {f['archivo'] for f in r['fuentes']}=={'dni_mayor_estado_civil.txt'}
    assert {main,'apellido'} <= {f['regla'] for f in r['fuentes']}
    assert 'acta de nacimiento original' in r['respuesta']
    assert 'solo si' in r['respuesta'].lower()
    assert '¿Desea recuperar' not in r['respuesta'] and not prompts

PERU='Soy adulto y necesito actualizar mi estado civil a viudo en mi DNI. Mi esposa falleció en Perú. ¿Qué documentos debo presentar?'

@pytest.mark.parametrize('query,main',[(DIVORCE,'divorcio'),(WIDOW,'italiano'),(PERU,'viudez_peru')])
@pytest.mark.parametrize('choice,value', [('', ''),('Quiero recuperar mi apellido materno','si'),
                                        ('No quiero recuperar mi apellido materno','no')])
def test_condicion_opcional_separada_y_negacion_excluye_regla(query,main,choice,value,motor):
    service,_,prompts=motor
    r=service.responder(query+' '+choice)
    c=snapshot(service,r['session_id'])['contexto_canonico']
    assert not c['pendientes'] and valor(c,'apellido')==value
    rules={f['regla'] for f in r['fuentes']}
    assert main in rules and ('apellido' in rules)==(value!='no')
    assert ('acta de nacimiento original' in r['respuesta'])==(value!='no')
    if value=='':
        principal=r['respuesta'].split('**Recuperación del apellido')[0]
        assert 'acta de nacimiento' not in principal
        optional=r['respuesta'].split('**Recuperación del apellido')[1].split('**Condiciones')[0]
        assert 'solo si' in optional and 'Si desea recuperar' in optional
        assert 'Si se emitió en Perú' in optional
    if main=='divorcio':
        for fact in ['acta de matrimonio peruana original','anotación de disolución del divorcio',
                     'apostilla','12 meses']:
            assert fact.casefold() in r['respuesta'].casefold()
    if main=='italiano':
        for fact in ['plurilingüe','municipalidad italiana','Prefectura','sustituye',
                     'No necesita presentar una certificación consular',
                     'si está registrado en Perú','si está registrado en una oficina consular peruana']:
            assert fact.casefold() in r['respuesta'].casefold()
        assert 'otras nacionalidades, OBSERVACIÓN' not in r['respuesta']
    assert not prompts


def test_respuestas_explicitas_sin_pregunta_previa_actualizan_solo_condicion(motor):
    service,_,_=motor
    first=service.responder(DIVORCE)
    sid,token=first['session_id'],first['session_token']
    r=service.responder('No, ya utilizo mi apellido materno',sid,token)
    assert valor(snapshot(service,sid)['contexto_canonico'],'apellido')=='no'
    assert 'acta de nacimiento' not in r['respuesta']
    r=service.responder('Me equivoqué, quiero recuperar mi apellido materno',sid,token)
    assert valor(snapshot(service,sid)['contexto_canonico'],'apellido')=='si'
    assert 'acta de nacimiento original' in r['respuesta']


@pytest.mark.parametrize('answer',['sí','no'])
def test_binaria_sin_aclaracion_no_confirma_apellido(answer,motor):
    service,_,_=motor
    first=service.responder(WIDOW)
    r=service.responder(answer,first['session_id'],first['session_token'])
    assert not valor(snapshot(service,r['session_id'])['contexto_canonico'],'apellido')
    assert 'solo si' in r['respuesta']


def test_contradiccion_si_requiere_aclaracion(motor):
    service,_,_=motor
    first=service.responder(DIVORCE)
    r=service.responder('No necesito cambiar mi apellido. Quiero recuperar mi apellido materno',first['session_id'],first['session_token'])
    c=snapshot(service,r['session_id'])['contexto_canonico']
    assert c['pendientes']=={'adulto_apellido':'contradiccion'} and not r['fuentes']
    r=service.responder('No quiero recuperar mi apellido materno',first['session_id'],first['session_token'])
    assert not snapshot(service,r['session_id'])['contexto_canonico']['pendientes']
    assert 'apellido' not in {f['regla'] for f in r['fuentes']}


@pytest.mark.parametrize('variant',['ausente','obsoleta','contradictoria'])
@pytest.mark.parametrize('rule',['divorcio','apellido'])
def test_reglas_planificadas_invalidas_no_producen_obligaciones(variant,rule,motor):
    from copy import deepcopy
    service,retrieve,_=motor
    docs=deepcopy(retrieve.return_value)
    doc=next(d for d in docs if d['metadata']['archivo']=='dni_mayor_estado_civil.txt'
             and d['contenido'].startswith('[[REGLA:'+rule+']]'))
    if variant=='ausente': docs.remove(doc)
    elif variant=='obsoleta': doc['contenido']=doc['contenido'].replace('original','fotocopia simple')
    else: docs.append({**doc,'contenido':doc['contenido'].replace('original','fotocopia simple')})
    retrieve.return_value=docs
    r=service.responder(DIVORCE)
    assert not r['fuentes'] and r['verificacion'].startswith('abstencion_documental')
    assert 'fotocopia simple' not in r['respuesta']


def test_opcion_negada_no_exige_una_regla_que_no_se_utiliza(motor):
    service,retrieve,_=motor
    retrieve.return_value=[d for d in retrieve.return_value if not d['contenido'].startswith('[[REGLA:apellido]]')]
    r=service.responder(DIVORCE+' No quiero recuperar mi apellido materno')
    assert r['fuentes'] and 'divorcio' in {f['regla'] for f in r['fuentes']}
    assert 'acta de nacimiento' not in r['respuesta']


@pytest.mark.parametrize('query',[DIVORCE,WIDOW])
def test_verificador_no_convierte_apellido_opcional_en_obligatorio(query,motor):
    from app.graph.dni_graph import verificar_respuesta
    service,_,_=motor
    r=service.responder(query)
    checked=verificar_respuesta({**snapshot(service,r['session_id']),
        'respuesta_borrador':'Todas las personas deben presentar acta de nacimiento original y pagar 14 euros.'})
    assert checked['respuesta_final']==r['respuesta']
    assert checked['verificacion'].startswith('observada:')
    assert 'solo si' in checked['respuesta_final']


def test_solo_pregunta_por_dato_material_en_viudez(motor):
    service,_,_=motor
    r=service.responder('Soy adulto y quiero actualizar mi estado civil a viudo en mi DNI. ¿Qué documentos debo presentar?')
    c=snapshot(service,r['session_id'])['contexto_canonico']
    assert c['pendientes']=={'adulto_defuncion':'faltante'}
    assert 'apellido materno' not in r['respuesta'] and not r['fuentes']


@pytest.mark.parametrize('question',['¿Debo presentar el acta de nacimiento?',
    '¿Y el acta de matrimonio?', '¿Qué documentos de defunción debo presentar?'])
def test_repreguntas_documentales_no_convierten_opcion_en_general(question,motor):
    service,_,_=motor
    first=service.responder(WIDOW)
    r=service.responder(question,first['session_id'],first['session_token'])
    assert 'solo si' in r['respuesta']
    assert {f['archivo'] for f in r['fuentes']}=={'dni_mayor_estado_civil.txt'}
    assert not valor(snapshot(service,r['session_id'])['contexto_canonico'],'apellido')


@pytest.mark.parametrize('question',['¿Cuánto cuesta?','¿Dónde solicito la cita?'])
def test_coste_y_cita_no_autorizan_apellido(question,motor):
    service,_,_=motor
    first=service.responder(DIVORCE)
    r=service.responder(question,first['session_id'],first['session_token'])
    assert {f['regla'] for f in r['fuentes']}=={'general'}
    c=snapshot(service,r['session_id'])['contexto_canonico']
    assert valor(c,'transicion')=='divorcio' and not valor(c,'apellido')


def test_cambio_titular_y_sesion_no_reutilizan_opcion(motor):
    service,_,_=motor
    first=service.responder(WIDOW+' Quiero recuperar mi apellido materno')
    r=service.responder('Ahora quiero renovar el DNI de mi hijo menor',first['session_id'],first['session_token'])
    assert r['intencion']=='dni_menor_renovacion'
    assert not snapshot(service,r['session_id'])['contexto_canonico']['condiciones_adulto']
    other=service.responder(DIVORCE)
    assert other['session_id']!=first['session_id']
    assert not valor(snapshot(service,other['session_id'])['contexto_canonico'],'apellido')
