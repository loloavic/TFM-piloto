"""Fixtures candidatos escritos explícitamente; no convertidor de V2.2."""
from copy import deepcopy
import json

from pydantic import ValidationError
import pytest

from app.graph.interpretation_candidate import InterpretacionCandidata, validar_candidata
from app.graph.interpretation_contract import validar_interpretacion
from app.graph.interpretation_adapter import adaptar_interpretacion
from app.graph.context_policy import ruta_documental
from app.graph.interpretation_diagnostics import diagnosticar_validacion
from scripts.v2_interpretation_scenarios import ESCENARIOS, atom, packet, request

from scripts.v23_interpretation_scenarios import (
    VERSION, META, fact, uncertain, support, operation, p, objective, clear, CASES,
)


@pytest.mark.parametrize('code,index,payload',[(code,i,t) for code,turns in CASES.items() for i,t in enumerate(turns,1)])
def test_matriz_14_29_representable_sin_cambiar_rutas_activas(code,index,payload):
    before=deepcopy(payload)
    result=validar_candidata(payload)
    assert result.valida and payload==before
    assert result.interpretacion.version==VERSION
    # La candidata NO es entrada del adaptador activo, incluso si es clara.
    assert not ruta_documental(adaptar_interpretacion(None,META,result.interpretacion.model_dump()))


def test_cobertura_matriz_sin_reescribir_expectativas():
    assert set(CASES)=={s.codigo for s in ESCENARIOS}
    assert sum(map(len,CASES.values()))==29
    for scenario in ESCENARIOS:assert len(CASES[scenario.codigo])==len(scenario.turnos)


def test_objetivo_no_requiere_familia_o_edad_artificiales():
    result=validar_candidata(p(objetivo=objective()))
    assert result.valida and result.interpretacion.objetivo.identificacion=='explicito_unico'
    assert result.interpretacion.relacion.estado==result.interpretacion.edad.estado=='no_mencionado'
    assert not hasattr(result,'ruta_documental') and not hasattr(result,'suficiente')


def test_relacion_incierta_no_invalida_identificacion_del_objetivo():
    result=validar_candidata(dict(clear(),relacion=uncertain()))
    assert result.valida and result.estado_linguistico=='incierto'
    assert result.interpretacion.objetivo.identificacion=='explicito_unico'
    assert result.interpretacion.edad.valor=='menor'


@pytest.mark.parametrize('kind',['multiple','ambiguo'])
def test_objetivo_no_resuelto_nunca_se_selecciona(kind):
    result=validar_candidata(dict(clear(),objetivo=objective(kind)))
    assert result.valida and result.estado_linguistico=='incierto'
    assert not ruta_documental(adaptar_interpretacion(None,META,result.interpretacion.model_dump()))


def test_misma_operacion_negada_y_solicitada_se_conserva_contradictoria():
    result=validar_candidata(p(operaciones={'renovacion':{'solicitud':support(),'negacion':support()}}))
    assert result.valida and result.estado_linguistico=='contradictorio'
    op=result.interpretacion.operaciones.renovacion
    assert op.solicitud is not None and op.negacion is not None


def test_varias_solicitudes_no_se_colapsan():
    result=validar_candidata(p(operaciones={**operation(),**operation('primera_vez')}))
    assert result.valida and result.estado_linguistico=='incierto'


def test_observacion_y_aclaracion_no_crean_aceptacion():
    for act in ('observacion','aclaracion','negacion'):
        result=validar_candidata(p(operaciones=operation(act=act)))
        assert result.valida
        op=result.interpretacion.operaciones.renovacion
        assert op.solicitud is None and getattr(op,act) is not None


def test_sujetos_y_origen_no_se_fusionan():
    result=validar_candidata(p(operaciones={'renovacion':{
        'solicitud':support(),'negacion':support(subject='acompanante'),
        'observacion':support(origin='referencia_contextual')}}))
    assert result.valida and result.estado_linguistico=='coherente'
    op=result.interpretacion.operaciones.renovacion
    assert op.negacion.sujeto=='acompanante'
    assert op.observacion.origen=='referencia_contextual'
    assert op.solicitud.origen=='explicito_turno'


def test_dni_previo_y_procedimiento_no_se_deciden_en_validador_linguistico():
    result=validar_candidata(p(dni_previo=fact('no'),operaciones=operation()))
    assert result.valida and result.estado_linguistico=='coherente'
    assert result.interpretacion.dni_previo.valor=='no'  # Futuro canónico debe comprobar compatibilidad.


def test_contexto_heredado_no_es_evidencia_nueva():
    result=validar_candidata(p(objetivo=objective('referencia_contextual','actual'),
                              edad=fact('menor',origin='referencia_contextual')))
    assert result.valida and result.interpretacion.edad.origen=='referencia_contextual'
    assert result.interpretacion.objetivo.identificacion=='referencia_contextual'


def test_ausencia_no_aplicabilidad_y_contradiccion_son_distintas():
    result=validar_candidata(p(relacion={'estado':'no_aplicable'},edad=uncertain('contradictorio')))
    assert result.valida and result.estado_linguistico=='contradictorio'
    assert result.interpretacion.dni_previo.estado=='no_mencionado'
    assert result.interpretacion.relacion.estado=='no_aplicable'


@pytest.mark.parametrize('payload',[
    p(edad=fact('25')),p(edad=fact(True)),p(edad={'estado':'no_mencionado','valor':'menor'}),
    p(edad={'estado':'determinado','valor':'menor'}),p(edad=dict(uncertain(),valor='menor')),
    p(objetivo=objective('referencia_contextual','otro')),
    p(objetivo=objective('multiple','actual')),p(operaciones={'pasaporte':{}}),
    p(nombre='SENSITIVE_SENTINEL'),p(edad=dict(fact('menor'),nombre='SENSITIVE_SENTINEL')),
    p(confianza=1.0),p(ruta='dni_menor_renovacion'),p(faltantes=['edad']),
    p(no_mencionadas=['edad']),dict(packet(*request())),
])
def test_candidata_invalida_no_filtra_datos(payload,caplog):
    result=validar_candidata(payload)
    assert not result.valida and result.interpretacion is None
    assert 'SENSITIVE_SENTINEL' not in repr(result)+caplog.text


@pytest.mark.parametrize('payload,code',[
    ('not-json','json_invalido'),(None,'tipo_invalido'),([], 'tipo_invalido'),
    ('x'*16385,'limite_excedido'),
    ('{"version":"2.3-candidata-1","edad":{},"edad":{}}','clave_duplicada'),
    ('{"version":"2.3-candidata-1","operaciones":{"renovacion":{"negacion":null,"negacion":null}}}','clave_duplicada'),
])
def test_json_estricto_sin_ultima_clave_ganadora(payload,code):
    assert validar_candidata(payload).codigo==code


def test_sin_deduplicacion_o_conversion_implicita():
    candidate=InterpretacionCandidata.model_construct(version=VERSION)
    assert validar_candidata(candidate).codigo=='tipo_invalido'
    assert validar_candidata(p()).estado_linguistico=='sin_evidencia'
    assert validar_candidata(json.dumps(clear())).valida
    assert validar_interpretacion(META,clear()).interpretacion is None


@pytest.mark.parametrize('field,value',[
    ('evidencias',None),('faltantes','edad'),('contradicciones','documento'),
    ('no_mencionadas','relacion'),('no_aplicables','funcion_documento'),
])
def test_duplicados_en_cinco_listas_con_codigo_especifico(field,value):
    payload=packet(*request())
    if field=='evidencias':payload[field].append(deepcopy(payload[field][0]))
    else:payload[field]=[value,value]
    before=deepcopy(payload)
    codes=diagnosticar_validacion(META,payload)
    assert 'duplicado' in codes and 'duplicado_'+field in codes
    assert payload==before
    assert validar_interpretacion(META,payload).interpretacion is None


def test_diagnostico_reporta_todas_las_listas_repetidas_sin_valores():
    payload=packet(atom('ambito','dni'),atom('ambito','dni'))
    for field,value in [('faltantes','edad'),('contradicciones','edad'),
                        ('no_mencionadas','relacion'),('no_aplicables','funcion_documento')]:
        payload[field]=[value,value]
    assert set(diagnosticar_validacion(META,payload))=={'duplicado',
        'duplicado_evidencias','duplicado_faltantes','duplicado_contradicciones',
        'duplicado_no_mencionadas','duplicado_no_aplicables'}


@pytest.mark.parametrize('key,value',[('acto','negacion'),('acto','observacion'),
    ('origen','referencia_contextual'),('sujeto','otro')])
def test_diferencias_semanticas_no_son_duplicados(key,value):
    original=atom('operacion','renovacion','solicitud_afirmativa')
    payload=packet(original,dict(original,**{key:value}))
    assert not any(c.startswith('duplicado') for c in diagnosticar_validacion(META,payload))


def test_codigo_especifico_atraviesa_evaluador_sin_cambiar_decision():
    from app.services.interpretation_service import InterpretationService
    from scripts.evaluate_v2_interpretation import evaluar,ProveedorSimulado
    class Repeated(ProveedorSimulado):
        def create(self,**kwargs):
            self.salida=deepcopy(self.salida)
            self.salida['no_mencionadas']=['relacion','relacion']
            return super().create(**kwargs)
    fake=Repeated()
    report=evaluar(InterpretationService(client=fake),modalidad='simulada',simulado=fake,
                   diagnostico=True,escenarios=ESCENARIOS[:1])
    assert not report['satisfactoria']
    for row in report['resultados']:
        assert row['diagnostico']['errores_validacion']==['duplicado','duplicado_no_mencionadas']
        assert not row['ruta_obtenida'] and row['diagnostico']['evidencias']==[]


def test_solicitud_nueva_y_negacion_contextual_no_se_confunden_con_negacion_actual():
    result=validar_candidata(p(operaciones={'renovacion':{
        'solicitud':support(),'negacion':support(origin='referencia_contextual')}}))
    assert result.valida and result.estado_linguistico=='coherente'
    op=result.interpretacion.operaciones.renovacion
    assert op.solicitud.origen=='explicito_turno' and op.negacion.origen=='referencia_contextual'
    # Resolver vigencia y posible rehabilitación sigue siendo tarea canónica futura.


def test_duplicados_tipados_no_quedan_ocultos_por_campo_extra_privado(caplog):
    payload=packet(*request());payload['no_mencionadas']=['relacion','relacion']
    payload['SENSITIVE_FIELD']='PRIVATE_VALUE'
    codes=diagnosticar_validacion(META,payload)
    assert 'campo_extra' in codes and 'duplicado_no_mencionadas' in codes
    assert 'PRIVATE' not in repr(codes) and 'SENSITIVE' not in repr(codes)+caplog.text
    assert validar_interpretacion(META,payload).interpretacion is None


def test_instancia_anidada_construida_no_elude_revalidacion():
    from app.graph.interpretation_candidate import Soporte
    unsafe=Soporte.model_construct(origen='SENSITIVE_SENTINEL',sujeto='objetivo')
    result=validar_candidata(p(operaciones={'renovacion':{'solicitud':unsafe}}))
    assert not result.valida and 'SENSITIVE_SENTINEL' not in repr(result)


def test_esquema_candidato_sin_bolsas_de_evidencias_o_requisitos():
    schema=InterpretacionCandidata.model_json_schema()
    assert not {'titular','evidencias','faltantes','contradicciones','no_mencionadas','no_aplicables'} & schema['properties'].keys()
    def check(node):
        if isinstance(node,dict):
            assert node.get('type')!='array'
            if node.get('type')=='object':assert node['additionalProperties'] is False
            for value in node.values():check(value)
        elif isinstance(node,list):
            for value in node:check(value)
    check(schema)
