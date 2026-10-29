"""Regla operativa 29/10/2026 y renovación adulta sin requisitos inventados."""
import pytest
from app.graph.classification import clasificar
from app.graph.adult_context import valor
from tests.test_adult_dni import motor, snapshot

@pytest.mark.parametrize('text,expected',[
    ('Mi DNI está vencido','vencido'),
    ('A mi DNI le quedan 60 días de vigencia','hasta_60'),
    ('Mi DNI vence en 59 días','hasta_60'),
    ('Mi DNI vence en 61 días','mas_60'),
    ('Mi DNI tiene seis meses de vigencia restantes','mas_60'),
])
def test_vigencia_categorica(text,expected):
    s=clasificar({'pregunta':'Soy adulto y quiero renovar mi DNI. '+text})
    assert valor(s['contexto_canonico'],'vigencia')==expected

@pytest.mark.parametrize('bad',[
    'Debe presentar su documento de identidad anterior.',
    'Debe pagar 14 euros.',
    'Debe presentar cuatro fotografías.',
    'Es obligatorio presentar un certificado de domicilio.',
])
def test_renovacion_no_admite_requisitos_inventados(bad,motor,monkeypatch):
    from app.graph import dni_graph
    service,_,_=motor
    class Hostile:
        def generar_respuesta(self,prompt): return bad
    monkeypatch.setattr(dni_graph,'LLMService',Hostile)
    r=service.responder('Buenos días, tengo 45 años y necesito renovar mi DNI peruano. ¿Cuánto cuesta y qué documentos debo presentar?')
    assert bad not in r['respuesta']
    assert '€7' in r['respuesta'] and 'Dos fotografías' in r['respuesta']
    assert 'identidad anterior' not in r['respuesta']


def test_renovacion_no_procede_con_61_dias(motor):
    service,_,_=motor
    r=service.responder('Soy adulto y quiero renovar mi DNI. Vence en 61 días. ¿Qué requisitos debo presentar?')
    assert 'no corresponde' in r['respuesta'].lower()
    assert '61' not in str(snapshot(service,r['session_id'])['contexto_canonico'])

@pytest.mark.parametrize('validity,files',[
    ('Mi DNI está vencido',{'dni_mayor_rectificacion.txt','dni_mayor_renovacion.txt'}),
    ('Mi DNI vence en 60 días',{'dni_mayor_rectificacion.txt','dni_mayor_renovacion.txt'}),
    ('Mi DNI vence en 59 días',{'dni_mayor_rectificacion.txt','dni_mayor_renovacion.txt'}),
    ('Mi DNI vence en 61 días',{'dni_mayor_rectificacion.txt'}),
    ('Mi DNI tiene seis meses de vigencia restantes',{'dni_mayor_rectificacion.txt'}),
])
def test_rectificacion_selecciona_solo_modalidades_procedentes(validity,files,motor):
    service,_,_=motor
    r=service.responder('Soy adulto y necesito rectificar mi fecha de nacimiento en el DNI. '+validity+'. ¿Qué documentos debo presentar?')
    assert {f['archivo'] for f in r['fuentes']}==files
    assert snapshot(service,r['session_id'])['operacion_dni']=='rectificacion'
    if len(files)>1:
        for fact in ['puede incorporar','partida de nacimiento original apostillada','12 meses','copia certificada','no se confirma que deba pagar dos tasas']:
            assert fact in r['respuesta']


def test_consulta_combinada_importe_y_documentos(motor):
    service,_,_=motor
    r=service.responder('Soy mayor de edad y necesito rectificar mi fecha de nacimiento en el DNI, pero mi documento está vencido. ¿Qué requisitos debo presentar y cuánto cuesta?')
    for fact in ['corresponde renovar','puede incorporar','partida de nacimiento original apostillada','12 meses','copia certificada','No puedo confirmar el importe total','No se confirma que deba pagar dos tasas']:
        assert fact in r['respuesta']
    assert '14' not in r['respuesta']
    assert snapshot(service,r['session_id'])['contexto_canonico']['pendientes']=={}


def test_vigencia_pendiente_se_completa_sin_fecha(motor):
    service,_,_=motor
    first=service.responder('Soy adulto y quiero renovar mi DNI y rectificar mis nombres. ¿Cuánto cuesta?')
    assert not first['fuentes'] and '60 días' in first['respuesta']
    r=service.responder('Vence en 59 días',first['session_id'],first['session_token'])
    assert {f['archivo'] for f in r['fuentes']}=={'dni_mayor_renovacion.txt','dni_mayor_rectificacion.txt'}
    assert 'No puedo confirmar el importe total' in r['respuesta']
    assert 'fecha exacta' not in r['respuesta']


def test_no_rehabilitar_renovacion_rechazada_con_vigencia(motor):
    service,_,_=motor
    first=service.responder('Soy adulto y quiero rectificar mi fecha de nacimiento en el DNI vencido.')
    service.responder('No quiero renovar',first['session_id'],first['session_token'])
    r=service.responder('Le quedan 59 días de vigencia',first['session_id'],first['session_token'])
    assert not r['fuentes']
    assert 'renovacion' in snapshot(service,first['session_id'])['contexto_canonico']['rechazadas']


@pytest.mark.parametrize('text', ['Mi acta tiene 61 días de emisión','Faltan 61 días para mi cita'])
def test_dias_de_otros_documentos_no_son_vigencia_dni(text):
    s=clasificar({'pregunta':'Soy adulto y quiero renovar mi DNI. '+text})
    assert not valor(s['contexto_canonico'],'vigencia')


def test_cambio_titular_y_sesion_no_heredan_vigencia(motor):
    service,_,_=motor
    first=service.responder('Soy adulto y quiero renovar mi DNI. Vence en 61 días.')
    r=service.responder('Ahora quiero renovar el DNI de mi hijo menor',first['session_id'],first['session_token'])
    assert r['intencion']=='dni_menor_renovacion'
    assert not valor(snapshot(service,first['session_id'])['contexto_canonico'],'vigencia')
    other=service.responder('Soy adulto y quiero renovar mi DNI. ¿Cuánto cuesta?')
    assert other['session_id']!=first['session_id']
    assert not valor(snapshot(service,other['session_id'])['contexto_canonico'],'vigencia')
    assert '€7' in other['respuesta']


@pytest.mark.parametrize('bad',['Debe presentar su DNI anterior.','El total es 14 euros.','Debe presentar cuatro fotografías.'])
def test_verificador_renovacion_reemplaza_borrador_hostil(bad,motor):
    from app.graph.dni_graph import verificar_respuesta
    service,_,_=motor
    r=service.responder('Soy adulto y quiero renovar mi DNI vencido. ¿Qué documentos debo presentar?')
    s=snapshot(service,r['session_id'])
    checked=verificar_respuesta({**s,'respuesta_borrador':bad})
    assert checked['respuesta_final']==r['respuesta']
    assert checked['verificacion'].startswith('observada:')
    assert checked['historial'][-1]['respuesta']!=bad

@pytest.mark.parametrize('days',[59,60])
def test_renovacion_procedente_con_umbral_inclusivo(days,motor):
    service,_,prompts=motor
    r=service.responder(f'Soy adulto y quiero renovar mi DNI. Vence en {days} días. ¿Cuánto cuesta y qué documentos debo presentar?')
    assert r['intencion']=='dni_adulto_renovacion' and r['fuentes']
    assert '€7' in r['respuesta'] and 'Dos fotografías' in r['respuesta']
    assert not prompts and 'no corresponde renovar' not in r['respuesta']


def test_renovacion_desconocida_no_afirma_elegibilidad(motor):
    service,_,_=motor
    r=service.responder('Soy adulto y quiero renovar mi DNI. ¿Cuánto cuesta?')
    assert not valor(snapshot(service,r['session_id'])['contexto_canonico'],'vigencia')
    assert 'si el DNI está vencido' in r['respuesta']
    assert '60 días' in r['respuesta'] and '€7' in r['respuesta']


@pytest.mark.parametrize('query',['¿Cuánto demora?','¿Dónde solicito cita?'])
def test_renovacion_no_procedente_no_se_omite_al_cambiar_tema(query,motor):
    service,_,_=motor
    first=service.responder('Soy adulto y quiero renovar mi DNI. Vence en 61 días.')
    r=service.responder(query,first['session_id'],first['session_token'])
    assert 'no corresponde renovar' in r['respuesta']
    assert '3 a 4 meses' not in r['respuesta']


@pytest.mark.parametrize('text,category',[
    ('Mi DNI no está vencido; vence en 59 días','hasta_60'),
    ('Mi DNI vence en dos meses','vigente'),
    ('Mi DNI está vencido y vence en 61 días',''),
])
def test_negacion_unidades_y_contradiccion(text,category):
    s=clasificar({'pregunta':'Soy adulto y quiero renovar mi DNI. '+text})
    assert valor(s['contexto_canonico'],'vigencia')==category
    if not category:
        assert s['requiere_aclaracion']
        assert 'adulto_vigencia' in s['contexto_canonico']['pendientes']


def test_regla_sin_autorizacion_del_umbral_no_habilita_plantilla(motor):
    from app.graph.presentation import renovacion_adulta
    service,_,_=motor
    r=service.responder('Soy adulto y quiero renovar mi DNI. ¿Cuánto cuesta?')
    c=snapshot(service,r['session_id'])['contexto_canonico']
    assert renovacion_adulta('Tasa €7. Dos fotografías.',c,'¿Cuánto cuesta?') is None

@pytest.mark.parametrize('first,expected', [('vencido',{'dni_mayor_rectificacion.txt','dni_mayor_renovacion.txt'}),
    ('vigente con más de 60 días',{'dni_mayor_rectificacion.txt'})])
def test_cambiar_operacion_del_mismo_titular_conserva_vigencia(first,expected,motor):
    service,_,_=motor
    r=service.responder('Soy adulto y quiero renovar mi DNI. Mi DNI está '+first+'.')
    before=snapshot(service,r['session_id'])['contexto_canonico']['condiciones_adulto']['vigencia']
    r=service.responder('Ahora solo quiero rectificar mi fecha de nacimiento en el DNI',r['session_id'],r['session_token'])
    after=snapshot(service,r['session_id'])['contexto_canonico']['condiciones_adulto']['vigencia']
    assert after==before
    assert {f['archivo'] for f in r['fuentes']}==expected


def test_opcion_documentada_de_direccion_no_se_pierde(motor):
    service,_,_=motor
    r=service.responder('Soy adulto y quiero renovar mi DNI vencido y cambiar mi dirección.')
    assert 'Puede solicitar cambio de dirección durante la renovación.' in r['respuesta']
    assert 'certificado de domicilio' not in r['respuesta']
