"""Corpus aportado y proveedor simulado; no llamadas externas ni datos reales."""
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.graph.classification import clasificar
from app.graph.context_policy import ruta_documental, validar_contexto
from app.graph.adult_context import plan, valor


def turn(state, text):
    return clasificar({**state, 'pregunta': text})


@pytest.fixture
def motor(monkeypatch, entorno_aislado):
    from app.graph import dni_graph
    from app.rag.document_loader import cargar_documentos_txt
    from app.rag.text_splitter import dividir_documentos
    docs = [{'contenido': f['contenido'], 'score': 0.1,
             'metadata': {'archivo': f['archivo'], 'chunk': f['chunk']}}
            for f in dividir_documentos(cargar_documentos_txt())]
    retrieve = Mock(return_value=docs)
    prompts = []
    class Local:
        def generar_respuesta(self, prompt):
            prompts.append(prompt)
            return 'Respuesta simulada para comprobar fuentes y transiciones.'
    monkeypatch.setattr(dni_graph, 'recuperar_contexto', retrieve)
    monkeypatch.setattr(dni_graph, 'LLMService', Local)
    return entorno_aislado, retrieve, prompts


def snapshot(service, sid):
    return service.grafo.get_state({'configurable': {'thread_id': sid}}).values


@pytest.mark.parametrize('q,intent', [
    ('Soy adulto y quiero renovar mi DNI', 'dni_adulto_renovacion'),
    ('Quiero renovar el DNI de mi hijo menor', 'dni_menor_renovacion'),
    ('Soy adulto y quiero rectificar los nombres en mi DNI', 'dni_adulto_rectificacion'),
    ('Soy adulto y quiero rectificar mi fecha de nacimiento en el DNI', 'dni_adulto_rectificacion'),
    ('Soy adulto y quiero cambiar la dirección de mi DNI', 'dni_adulto_rectificacion'),
    ('Soy adulto y quiero actualizar la firma de mi DNI', 'dni_adulto_rectificacion'),
])
def test_clasificacion_documentada(q, intent):
    s = turn({}, q)
    assert s['intencion'] == intent
    assert validar_contexto(s['contexto_canonico'])


@pytest.mark.parametrize('q', ['Quiero renovar mi DNI', 'Quiero rectificar mi DNI',
    'Necesito renovar el DNI de mi hijo'])
def test_edad_desconocida_no_se_infiere_adulto(q, motor):
    service, retrieve, prompts = motor
    r = service.responder(q)
    assert r['intencion'] == 'general' and not r['fuentes']
    assert not retrieve.called and not prompts


@pytest.mark.parametrize('case,expected,absent', [
    ('Me casé en Perú', {'matrimonio_peru'}, {'matrimonio_extranjero','divorcio','apellido'}),
    ('Me casé en Italia', {'matrimonio_extranjero'}, {'matrimonio_peru','divorcio','apellido'}),
    ('Me divorcié y quiero recuperar el apellido materno', {'divorcio','apellido'}, {'matrimonio_peru','viudez_peru'}),
    ('Me divorcié y no quiero recuperar el apellido materno', {'divorcio'}, {'apellido','viudez_peru'}),
    ('Soy viudo, mi esposa falleció en Perú y no quiero recuperar el apellido materno', {'viudez_peru'}, {'apellido','viudez_italia','italiano'}),
    ('Soy viuda, mi esposo falleció en Italia, mi esposo era italiano y quiero recuperar el apellido materno', {'viudez_italia','italiano','apellido'}, {'viudez_peru','matrimonio_peru'}),
    ('Soy viuda, mi esposo falleció en Italia, mi esposo no era italiano y no quiero recuperar el apellido materno', {'viudez_italia'}, {'italiano','apellido','viudez_peru'}),
    ('Soy viudo, mi esposa falleció en otro país y no quiero recuperar el apellido materno', {'viudez_otro'}, {'italiano','viudez_peru'}),
])
def test_estado_civil_solo_reglas_aplicables(case, expected, absent, motor):
    service, _, prompts = motor
    r = service.responder('Soy adulto y quiero cambiar el estado civil de mi DNI. ' + case)
    assert r['intencion'] == 'dni_adulto_rectificacion'
    assert {f['archivo'] for f in r['fuentes']} == {'dni_mayor_estado_civil.txt'}
    rules = {f['regla'] for f in r['fuentes']}
    assert rules == expected | {'general'} and not rules & absent
    if 'italiano' in rules:
        assert 'OBSERVACIÓN PENDIENTE' not in r['respuesta'] and not prompts
    elif 'viudez_italia' in rules or 'viudez_otro' in rules:
        assert 'No puedo confirmar' in r['respuesta'] and not prompts
    elif rules & {'divorcio', 'viudez_peru'}:
        assert not prompts and 'Documentación principal' in r['respuesta']
    else:
        assert prompts


@pytest.mark.parametrize('name', ['nombres','apellidos','fecha de nacimiento','lugar de nacimiento','datos de padres'])
def test_rectificacion_datos_requisitos_y_procedencia(name, motor):
    service, _, prompts = motor
    r = service.responder('Soy adulto y quiero rectificar ' + name + ' en mi DNI')
    assert {f['regla'] for f in r['fuentes']} == {'general', 'datos'}
    context = prompts[-1].split('CONTEXTO DOCUMENTAL:\n')[1].split('PREGUNTA ACTUAL')[0]
    assert '12 meses' in context and 'copia certificada' in context and 'original apostillada' in context
    assert 'dni_menor' not in str(r['fuentes'])


@pytest.mark.parametrize('q', [
    'Soy adulto y quiero renovar mi DNI vencido y rectificar mis nombres',
    'Soy adulto y quiero rectificar los nombres en mi DNI vencido',
])
def test_combinacion_solo_derivacion_documentada(q, motor):
    service, _, prompts = motor
    r = service.responder(q)
    assert {f['archivo'] for f in r['fuentes']} == {'dni_mayor_renovacion.txt','dni_mayor_rectificacion.txt'}
    assert not prompts  # El alcance combinado se controla ahora sin síntesis LLM.
    assert 'partida de nacimiento original apostillada' in r['respuesta']
    assert 'no es una lista combinada definitiva' in r['respuesta']


@pytest.mark.parametrize('q', [
    'Soy adulto y quiero renovar mi DNI y rectificar mis nombres',
    'Soy adulto y quiero renovar mi DNI y cambiar mi estado civil',
])
def test_combinaciones_no_verificadas_no_generan(q, motor):
    service, _, prompts = motor
    r = service.responder(q)
    assert not r['fuentes'] and not prompts
    assert ('60 días' in r['respuesta'] if 'mis nombres' in q else 'no está confirmada' in r['respuesta'])


def test_fuente_parcial_combinada_no_basta(motor):
    service, retrieve, prompts = motor
    retrieve.return_value = [d for d in retrieve.return_value if d['metadata']['archivo'] != 'dni_mayor_rectificacion.txt']
    r = service.responder('Soy adulto y quiero renovar mi DNI vencido y rectificar mis nombres')
    assert not r['fuentes'] and not prompts
    assert 'No cuento con información documental suficiente' in r['respuesta']


def test_aclaraciones_civiles_incrementales_y_coste(motor):
    service, retrieve, prompts = motor
    first = service.responder('Soy adulto y quiero cambiar el estado civil de mi DNI')
    sid, token = first['session_id'], first['session_token']
    assert not retrieve.called
    r = service.responder('Me casé', sid, token)
    assert not r['fuentes'] and not retrieve.called
    r = service.responder('Me casé en Perú', sid, token)
    assert {f['regla'] for f in r['fuentes']} == {'general','matrimonio_peru'}
    r = service.responder('¿Cuánto cuesta?', sid, token)
    assert {f['regla'] for f in r['fuentes']} == {'general'}
    assert snapshot(service,sid)['contexto_canonico']['tema'] == 'coste'


def test_cambio_transicion_invalida_condiciones_dependientes(motor):
    service, _, _ = motor
    first = service.responder('Soy adulto y quiero cambiar el estado civil de mi DNI. Me casé en Perú')
    sid, token = first['session_id'], first['session_token']
    r = service.responder('Me divorcié', sid, token)
    c = snapshot(service,sid)['contexto_canonico']
    assert not c['pendientes'] and not valor(c,'apellido')
    assert {f['regla'] for f in r['fuentes']} == {'general','divorcio','apellido'}
    assert not valor(c,'matrimonio')
    r = service.responder('No quiero recuperar el apellido materno', sid, token)
    assert {f['regla'] for f in r['fuentes']} == {'general','divorcio'}


def test_rechazo_operacion_no_reaparece_por_condiciones():
    s = turn({}, 'Soy adulto y quiero rectificar los nombres en mi DNI')
    s = turn(s, 'No quiero rectificar')
    s = turn(s, 'Mi DNI está vencido')
    assert 'rectificacion' in s['contexto_canonico']['rechazadas']
    assert s['operacion_dni'] != 'rectificacion'


def test_nuevo_titular_y_sesiones_no_heredan_condiciones(motor):
    service, _, _ = motor
    first = service.responder('Soy adulto y quiero cambiar el estado civil de mi DNI. Me casé en Perú')
    sid, token = first['session_id'], first['session_token']
    r = service.responder('Ahora quiero renovar el DNI de mi hijo menor',sid,token)
    c = snapshot(service,sid)['contexto_canonico']
    assert r['intencion'] == 'dni_menor_renovacion' and not c['condiciones_adulto']
    other = service.responder('Soy adulto y quiero cambiar el estado civil de mi DNI')
    assert not other['fuentes']
    assert not valor(snapshot(service,other['session_id'])['contexto_canonico'],'matrimonio')
    service.sessions.delete(sid,token)
    assert not list(service.grafo.checkpointer.list({'configurable':{'thread_id':sid}}))


def test_splitter_conserva_reglas_completas_y_cuatro_txt_anteriores():
    from app.rag.document_loader import cargar_documentos_txt
    from app.rag.text_splitter import dividir_documentos
    chunks=dividir_documentos(cargar_documentos_txt())
    assert len(list(Path('data/raw').glob('*.txt'))) == 7
    adult=[c for c in chunks if c['archivo'].startswith('dni_mayor_')]
    assert adult and all(c['contenido'].startswith('[[REGLA:') and c['contenido'].endswith('[[FIN]]') for c in adult)


@pytest.mark.parametrize('topic', ['¿Cuánto cuesta?', '¿Y las fotografías?', '¿Dónde solicito la cita?', '¿Cuánto demora?'])
def test_temascivil_sin_condiciones_incompatibles(topic, motor):
    service, _, _ = motor
    first = service.responder('Soy adulto y quiero cambiar el estado civil de mi DNI')
    r = service.responder(topic, first['session_id'], first['session_token'])
    assert {f['regla'] for f in r['fuentes']} == ({'plazo'} if 'demora' in topic else {'general'})


def test_aclaracion_edad_conserva_coste_civil(motor):
    service, _, prompts = motor
    first = service.responder('¿Cuánto cuesta cambiar el estado civil en mi DNI?')
    assert not first['fuentes']
    r = service.responder('Soy adulto',first['session_id'],first['session_token'])
    assert {f['regla'] for f in r['fuentes']} == {'general'}
    assert 'Consulta pendiente: ¿Cuánto cuesta?' in prompts[-1]


def test_aclaracion_guiada_lugar_y_transicion(motor):
    service, retrieve, _ = motor
    first = service.responder('Soy adulto y quiero cambiar el estado civil de mi DNI')
    sid, token=first['session_id'],first['session_token']
    service.responder('Casado',sid,token)
    assert not retrieve.called
    r=service.responder('En Perú',sid,token)
    assert {f['regla'] for f in r['fuentes']} == {'general','matrimonio_peru'}


def test_negacion_lugar_no_gana_a_rectificacion():
    s=turn({},'Soy adulto y quiero cambiar el estado civil de mi DNI. No me casé en Perú, me casé en Italia')
    assert valor(s['contexto_canonico'],'matrimonio') == 'extranjero'


def test_rectificacion_vencida_conserva_operacion_solicitada():
    s=turn({},'Soy adulto y quiero rectificar nombres en mi DNI vencido')
    assert s['operacion_dni'] == 'rectificacion'
    assert set(plan(s['contexto_canonico'])) == {'dni_mayor_rectificacion.txt','dni_mayor_renovacion.txt'}


@pytest.mark.parametrize('damage', ['revision','origen','valor'])
def test_condiciones_inconsistentes_bloquean_fuentes(damage):
    s=turn({},'Soy adulto y quiero cambiar el estado civil de mi DNI. Me casé en Perú')
    c=s['contexto_canonico']
    d=c['condiciones_adulto']['matrimonio']
    d[damage] = {'revision': 999, 'origen':'observacion', 'valor':'dato no permitido'}[damage]
    assert not validar_contexto(c) and not ruta_documental(c)


def test_lugares_alternativos_necesitan_confirmacion_nueva(motor):
    service, retrieve, _=motor
    r=service.responder('Soy adulto y quiero cambiar el estado civil de mi DNI. Matrimonio en Perú o en Italia')
    sid, token=r['session_id'],r['session_token']
    assert not r['fuentes'] and not retrieve.called
    r=service.responder('¿Cuánto cuesta?',sid,token)
    assert not r['fuentes'] and not retrieve.called
    r=service.responder('El matrimonio fue en Perú',sid,token)
    assert {f['regla'] for f in r['fuentes']} == {'general'}  # retoma coste


def test_modificaciones_simultaneas_no_se_eligen_arbitrariamente(motor):
    service, retrieve, _=motor
    r=service.responder('Soy adulto y quiero rectificar mis nombres y cambiar el estado civil de mi DNI')
    assert not r['fuentes'] and not retrieve.called
    c=snapshot(service,r['session_id'])['contexto_canonico']
    assert c['pendientes']['adulto_modificacion'] == 'contradiccion'
    assert validar_contexto(c)


def test_tasas_combinadas_no_se_suman(motor):
    service, _, prompts=motor
    first=service.responder('Soy adulto y quiero rectificar nombres en mi DNI vencido')
    before=len(prompts)
    r=service.responder('¿Cuánto cuesta?',first['session_id'],first['session_token'])
    assert 'No puedo confirmar el importe total' in r['respuesta']
    assert len(prompts) == before
    assert {f['archivo'] for f in r['fuentes']} == {'dni_mayor_renovacion.txt','dni_mayor_rectificacion.txt'}


def test_api_adultos_autorizacion_y_procedencia(motor):
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        r=client.post('/api/v1/consultas',json={'pregunta':'Soy adulto y quiero rectificar los nombres en mi DNI'})
        assert r.status_code == 200
        assert {f['archivo'] for f in r.json()['fuentes']} == {'dni_mayor_rectificacion.txt'}
        sid, token=r.json()['session_id'],r.headers['X-Session-Token']
        assert 'session_token' not in r.json()
        denied=client.post('/api/v1/consultas',json={'pregunta':'¿Cuánto cuesta?','session_id':sid})
        assert denied.status_code == 403
        assert client.delete('/api/v1/sesiones/'+sid,headers={'X-Session-Token':token}).status_code == 204


def test_indices_sin_marcadores_no_autorizan_fragmentos_de_adulto(motor):
    service, retrieve, prompts=motor
    retrieve.return_value=[{'contenido':'Requisitos sin reglas verificables', 'score':0.1,
        'metadata':{'archivo':'dni_mayor_renovacion.txt','chunk':0}}]
    r=service.responder('Soy adulto y quiero renovar mi DNI')
    assert not r['fuentes'] and not prompts


@pytest.mark.parametrize('observation,files', [
    ('Mi DNI está vencido', {'dni_mayor_rectificacion.txt','dni_mayor_renovacion.txt'}),
    ('Está vencido', {'dni_mayor_rectificacion.txt','dni_mayor_renovacion.txt'}),
    ('Ya tengo DNI', {'dni_mayor_rectificacion.txt'}),
])
def test_observacion_tenencia_complementa_rectificacion_no_la_sustituye(observation, files, motor):
    service, _, _=motor
    first=service.responder('Soy adulto y quiero rectificar nombres en mi DNI')
    r=service.responder(observation,first['session_id'],first['session_token'])
    assert snapshot(service,first['session_id'])['operacion_dni'] == 'rectificacion'
    assert {f['archivo'] for f in r['fuentes']} == files


def test_derivacion_documental_no_levanta_renovacion_rechazada(motor):
    service, retrieve, _=motor
    first=service.responder('Soy adulto y quiero rectificar nombres en mi DNI')
    sid,token=first['session_id'],first['session_token']
    service.responder('No quiero renovar',sid,token)
    before=retrieve.call_count
    r=service.responder('Mi DNI está vencido',sid,token)
    c=snapshot(service,sid)['contexto_canonico']
    assert not r['fuentes'] and retrieve.call_count == before
    assert 'renovacion' in c['rechazadas'] and 'adulto_derivacion' in c['pendientes']
    r=service.responder('Quiero renovar el DNI',sid,token)
    assert {f['archivo'] for f in r['fuentes']} == {'dni_mayor_rectificacion.txt','dni_mayor_renovacion.txt'}


REPORTED_ADULT_QUERY = ('Soy mayor de edad y necesito rectificar mi fecha de nacimiento en el DNI, '
    'pero el documento está vencido. ¿Qué requisitos debo presentar y cuánto cuesta?')


def test_titular_adulto_reportado_etapas_y_fuentes(motor):
    from app.graph.classification import normalizar, solicitante, extraer_evidencia
    holder, explicit, conflict = solicitante(normalizar(REPORTED_ADULT_QUERY))
    assert holder == {'grupo_edad':'adulto', 'destinatario':'propio'}
    assert explicit and not conflict
    e = extraer_evidencia(REPORTED_ADULT_QUERY)
    assert e.edad == 'adulto' and e.titular == 'propio' and e.operacion == 'rectificacion'
    s = turn({}, REPORTED_ADULT_QUERY)
    assert ruta_documental(s['contexto_canonico']) == 'dni_adulto_rectificacion'
    service, _, prompts = motor
    r = service.responder(REPORTED_ADULT_QUERY)
    assert r['intencion'] == 'dni_adulto_rectificacion'
    assert {f['archivo'] for f in r['fuentes']} == {'dni_mayor_rectificacion.txt','dni_mayor_renovacion.txt'}
    assert not prompts  # Tasa combinada: respuesta determinista sin sumar.
    assert 'No puedo confirmar el importe total' in r['respuesta']


@pytest.mark.parametrize('question,group,holder', [
    ('Soy mayor de edad y quiero rectificar mi DNI', 'adulto','propio'),
    ('Soy adulto y necesito corregir mi fecha de nacimiento', 'adulto','propio'),
    ('Tengo 45 años y necesito rectificar datos de mi DNI vencido', 'adulto','propio'),
    ('Mi padre es mayor de edad y necesita rectificar su DNI', 'adulto','adulto'),
    ('Soy menor de edad y necesito rectificar mi DNI', 'menor','propio'),
    ('Necesito rectificar mi DNI', '', 'propio'),
])
def test_variantes_titular_rectificacion(question, group, holder):
    from app.graph.classification import extraer_evidencia
    e=extraer_evidencia(question)
    assert e.edad == group and e.titular == holder
    s=turn({},question)
    if 'dni' in question.lower():
        assert s['operacion_dni'] == 'rectificacion'
    else:
        # No atribuir la fecha a un DNI si no se indicó el documento.
        assert s['requiere_aclaracion'] and not ruta_documental(s['contexto_canonico'])
        assert s['motivo_aclaracion'] == 'tramite'
    if group != 'adulto':
        assert not ruta_documental(s['contexto_canonico'])


@pytest.mark.parametrize('followup', ['¿Qué requisitos debo presentar?', '¿Cuánto cuesta?', '¿Qué documentación debo presentar?'])
def test_titular_reportado_repreguntas_y_cambio_a_menor(followup, motor):
    service, _, _=motor
    first=service.responder(REPORTED_ADULT_QUERY)
    sid,token=first['session_id'],first['session_token']
    r=service.responder(followup,sid,token)
    assert r['intencion'] == 'dni_adulto_rectificacion'
    assert {f['archivo'] for f in r['fuentes']} == {'dni_mayor_rectificacion.txt','dni_mayor_renovacion.txt'}
    r=service.responder('Ahora necesito renovar el DNI de mi hijo menor',sid,token)
    assert r['intencion'] == 'dni_menor_renovacion'
    assert {f['archivo'] for f in r['fuentes']} == {'dni_menor_renovacion.txt'}
    r=service.responder(REPORTED_ADULT_QUERY,sid,token)
    assert r['intencion'] == 'dni_adulto_rectificacion'
    assert {f['archivo'] for f in r['fuentes']} == {'dni_mayor_rectificacion.txt','dni_mayor_renovacion.txt'}


def test_titular_reportado_fuente_incompleta_sigue_absteniendose(motor):
    service,retrieve,prompts=motor
    retrieve.return_value=[d for d in retrieve.return_value if d['metadata']['archivo'] != 'dni_mayor_renovacion.txt']
    r=service.responder(REPORTED_ADULT_QUERY)
    assert not r['fuentes'] and not prompts
    assert 'No cuento con información documental suficiente' in r['respuesta']


@pytest.mark.parametrize('question,group,holder', [
    ('Mi madre es adulta y quiere corregir su DNI. ¿Qué requisitos debe presentar?', 'adulto','adulto'),
    ('Mi padre necesita rectificar su DNI', '', ''),
    ('Soy mayor de edad y debo presentar mi DNI para acompañar a mi hijo menor', 'menor','descendiente'),
    ('No soy mayor de edad; soy menor y necesito rectificar mi DNI. ¿Qué debo presentar?', 'menor','propio'),
])
def test_no_trasladar_edad_de_apoyo_ni_inferirla_por_parentesco(question, group, holder):
    from app.graph.classification import extraer_evidencia
    e=extraer_evidencia(question)
    assert e.edad == group and e.titular == holder


def test_edad_numerica_no_se_pierde_por_presentar_requisitos(motor):
    service, _, _=motor
    r=service.responder('Tengo 45 años y necesito rectificar datos de mi DNI vencido. ¿Qué requisitos debo presentar?')
    s=snapshot(service,r['session_id'])
    assert s['contexto_solicitante'] == {'grupo_edad':'adulto','destinatario':'propio'}
    assert s['operacion_dni'] == 'rectificacion'
    # «Datos» no distingue dirección, imagen/firma o datos personales.
    assert s['motivo_aclaracion'] == 'adulto_modificacion' and not r['fuentes']
