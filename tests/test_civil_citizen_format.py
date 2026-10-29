"""Formato ciudadano con ámbitos documentales explícitos, sin reformular por LLM."""
import pytest
from tests.test_adult_dni import motor, snapshot
from tests.test_optional_surname import DIVORCE, WIDOW

INTERNAL = ['No exigir adicionalmente otra acta de defunción por inferencia',
    'No confundir la acreditación del matrimonio con la defunción',
    'son condiciones independientes','Aplicar condiciones generales',
    'respete las condiciones indicadas','corpus','[[REGLA:', '.txt']

@pytest.mark.parametrize('query',[DIVORCE,WIDOW])
def test_sin_instrucciones_del_sistema_en_respuesta(query,motor):
    service,_,prompts=motor
    r=service.responder(query)
    for phrase in INTERNAL: assert phrase not in r['respuesta']
    assert not prompts


def test_formalidades_divorcio_junto_al_acta(motor):
    service,_,_=motor
    r=service.responder(DIVORCE)
    main=r['respuesta'].split('**Recuperación del apellido')[0]
    for fact in ['acta de matrimonio peruana original','apostilla','Ministerio de Relaciones Exteriores','12 meses','buen estado']:
        assert fact in main

@pytest.mark.parametrize('query',[DIVORCE,WIDOW])
@pytest.mark.parametrize('choice,value',[('', ''),('Quiero recuperar mi apellido materno','si'),
                                        ('No quiero recuperar mi apellido materno','no')])
def test_formato_no_cambia_decision_ni_documentos_opcionales(query,choice,value,motor):
    from app.graph.adult_context import valor
    service,_,prompts=motor
    r=service.responder(query+' '+choice)
    c=snapshot(service,r['session_id'])['contexto_canonico']
    assert valor(c,'apellido')==value and not c['pendientes']
    assert r['intencion']=='dni_adulto_rectificacion'
    assert {f['archivo'] for f in r['fuentes']}=={'dni_mayor_estado_civil.txt'}
    assert ('apellido' in {f['regla'] for f in r['fuentes']})==(value!='no')
    assert ('acta de nacimiento original' in r['respuesta'])==(value!='no')
    if value!='no':
        main,optional=r['respuesta'].split('**Recuperación del apellido',1)
        assert 'acta de nacimiento' not in main
        optional=optional.split('**Condiciones del trámite**')[0]
        assert ('solo si' in optional)==(value=='')
        assert 'Si se emitió en Perú:' in optional
        for fact in ['acta de nacimiento original','apostilla del Ministerio de Relaciones Exteriores',
                     '12 meses','buen estado']:
            assert fact in optional
    assert r['respuesta'].count('**Tasa individual:** €7.')==1
    assert r['respuesta'].count('https://bookeo.com/cturin?')==1
    assert r['respuesta'].count('Fotografía obligatoria:')==1
    for phrase in INTERNAL: assert phrase not in r['respuesta']
    assert not prompts


def test_ambitos_separados_de_formalidades_en_viudez_italiana(motor):
    service,_,_=motor
    r=service.responder(WIDOW)
    text=r['respuesta']
    death=text.split('**1. Documento de defunción')[1].split('**2. Documento de matrimonio')[0]
    marriage=text.split('**2. Documento de matrimonio')[1].split('**Recuperación del apellido')[0]
    peru,consular=marriage.split('- Si está registrado en una oficina consular peruana:')
    for forbidden in ['apostilla','Ministerio de Relaciones Exteriores','12 meses','buen estado']:
        assert forbidden not in death and forbidden not in consular
        assert forbidden in peru
    for fact in ['municipalidad italiana','Prefectura competente','únicamente','sustituye']:
        assert fact in death
    assert 'No necesita presentar una certificación consular de defunción adicional' in death
    assert 'copia certificada emitida por dicha oficina' in consular
    assert 'registro consular peruano' not in death  # Explicación no solicitada.


@pytest.mark.parametrize('place',['Perú','una oficina consular peruana'])
def test_alternativas_de_matrimonio_no_son_dos_documentos_universales(place,motor):
    service,_,_=motor
    r=service.responder(WIDOW+' Mi matrimonio está registrado en '+place+'.')
    section=r['respuesta'].split('**2. Documento de matrimonio')[1].split('**Recuperación')[0]
    lines=[line for line in section.splitlines() if line.startswith('- ')]
    assert len(lines)==2
    assert lines[0].startswith('- Si está registrado en Perú:')
    assert lines[1].startswith('- Si está registrado en una oficina consular peruana:')
    assert 'acta de matrimonio peruana original' in lines[0]
    assert 'copia certificada' in lines[1] and 'apostilla' not in lines[1]


@pytest.mark.parametrize('variant',['ausente','incompleta','obsoleta','contradictoria'])
@pytest.mark.parametrize('query,rule',[(DIVORCE,'divorcio'),(WIDOW,'italiano')])
def test_formato_no_salva_reglas_invalidas(variant,query,rule,motor):
    from copy import deepcopy
    service,retrieve,prompts=motor
    docs=deepcopy(retrieve.return_value)
    doc=next(d for d in docs if d['metadata']['archivo']=='dni_mayor_estado_civil.txt'
             and d['contenido'].startswith('[[REGLA:'+rule+']]'))
    if variant=='ausente': docs.remove(doc)
    elif variant=='incompleta': doc['contenido']=doc['contenido'].replace('[[FIN]]','')
    elif variant=='obsoleta': doc['contenido']=doc['contenido'].replace('original','fotocopia') if rule=='divorcio' else doc['contenido'].replace('legalizada','sin legalizar')
    else:
        bad=doc['contenido'].replace('original','fotocopia') if rule=='divorcio' else doc['contenido'].replace('legalizada','sin legalizar')
        docs.append({**doc,'contenido':bad})
    retrieve.return_value=docs
    r=service.responder(query)
    assert not r['fuentes'] and r['verificacion'].startswith('abstencion_documental')
    assert 'fotocopia' not in r['respuesta'] and 'sin legalizar' not in r['respuesta']
    assert not r['respuesta'].startswith('**Actualización del estado civil') and not prompts


@pytest.mark.parametrize('query',[DIVORCE,WIDOW])
def test_verificador_sigue_comparando_salida_final(query,motor):
    from app.graph.dni_graph import verificar_respuesta
    service,_,_=motor
    r=service.responder(query)
    for bad in ['Todas las actas italianas y consulares requieren apostilla peruana y 12 meses.',
                'Todas las personas deben presentar el acta de nacimiento y pagar 14 euros.']:
        verified=verificar_respuesta({**snapshot(service,r['session_id']),'respuesta_borrador':bad})
        assert verified['respuesta_final']==r['respuesta']
        assert verified['verificacion'].startswith('observada:')
        assert verified['historial'][-1]['respuesta']==r['respuesta']


def test_explicacion_de_registro_solo_si_se_pregunta(motor):
    service,_,_=motor
    first=service.responder(WIDOW)
    assert 'su fallecimiento no se registra' not in first['respuesta']
    r=service.responder('¿Por qué no necesito una certificación consular de defunción para mi DNI?',first['session_id'],first['session_token'])
    assert 'su fallecimiento no se registra como defunción de un ciudadano peruano' in r['respuesta']
    assert 'por inferencia' not in r['respuesta']


def test_cambio_de_intencion_y_sesion_nueva_conservan_contextos(motor):
    service,_,_=motor
    first=service.responder('Soy adulto y mi DNI vence dentro de 61 días. ¿Puedo renovarlo ahora?')
    before=snapshot(service,first['session_id'])['contexto_canonico']
    r=service.responder('Necesito actualizar mi estado civil a divorciado',first['session_id'],first['session_token'])
    after=snapshot(service,r['session_id'])['contexto_canonico']
    assert r['respuesta'].startswith('**Actualización del estado civil por divorcio**')
    for key in ['edad','titular']:
        assert after[key]==before[key]
    assert after['condiciones_adulto']['vigencia']==before['condiciones_adulto']['vigencia']
    assert not after['consulta_renovacion']
    other=service.responder(WIDOW+' No quiero recuperar mi apellido materno')
    assert other['session_id']!=r['session_id']
    assert 'acta de nacimiento' not in other['respuesta']
    assert 'acta de nacimiento original' in r['respuesta']


def test_otras_operaciones_no_reciben_formato_civil(motor):
    service,_,_=motor
    first=service.responder('Soy adulto y quiero renovar mi DNI vencido. ¿Cuánto cuesta?')
    assert first['respuesta'].startswith('**Tasa de renovación individual:** €7.')
    r=service.responder('Ahora quiero rectificar mi fecha de nacimiento en mi DNI. ¿Qué documentos debo presentar?',first['session_id'],first['session_token'])
    assert {f['archivo'] for f in r['fuentes']}=={'dni_mayor_renovacion.txt','dni_mayor_rectificacion.txt'}
    assert 'no son acumulables' in r['respuesta']
    assert 'partida de nacimiento original apostillada' in r['respuesta']
    assert '**Actualización del estado civil' not in r['respuesta']


def test_mencionar_registro_como_contexto_no_agrega_explicacion_no_pedida(motor):
    service,_,_=motor
    r=service.responder(WIDOW+' Mi matrimonio consta en el registro consular.')
    assert 'su fallecimiento no se registra' not in r['respuesta']
    assert r['respuesta'].startswith('**Actualización del estado civil por viudez**')

@pytest.mark.parametrize('query,formatter',[(DIVORCE,'divorcio_ciudadano'),(WIDOW,'viudez_italiana_ciudadana')])
def test_formato_no_interpretable_abstiene_sin_delegar_llm(query,formatter,motor,monkeypatch):
    from app.graph import combination_guard
    service,_,prompts=motor
    monkeypatch.setattr(combination_guard,formatter,lambda *args,**kwargs:None)
    r=service.responder(query)
    assert r['verificacion'].startswith('abstencion_documental')
    assert not r['respuesta'].startswith('**Actualización') and not prompts
