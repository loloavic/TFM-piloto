"""T1–T7: invariantes categóricas; sin frases reconocidas ni proveedor real."""
from copy import deepcopy

from jsonschema import Draft202012Validator
import pytest

from app.graph.context_policy import contexto_inicial, ruta_documental, validar_contexto
from app.graph.interpretation_adapter import adaptar_interpretacion
from app.graph.interpretation_contract import InterpretacionTurno
from app.services.interpretation_service import esquema_estricto
from scripts.v2_interpretation_scenarios import atom, packet, request

R='dni_menor_renovacion'

def step(c,p):
    before=deepcopy(c)
    n=adaptar_interpretacion(c,dict(turno=c['turno']+1 if c else 1,
                                  revision=c['revision'] if c else 0),p)
    assert validar_contexto(n) and c==before
    return n


def base():return step(None,packet(*request()))


def test_t1_identificacion_actual_no_requiere_historia():
    c=step(None,packet(*request(),atom('referencia_titular','actual')))
    assert ruta_documental(c)==R


def test_t2_ausencia_y_no_aplicabilidad_no_son_ambiguedad():
    p=packet(atom('ambito','dni'),atom('tema','seguimiento','solicitud_afirmativa'))
    p.update(version='2.2',no_mencionadas=['titular','operacion'],
             no_aplicables=['edad','funcion_documento'])
    assert ruta_documental(step(None,p))=='dni_consulta_estado'


def test_t3_recuperacion_con_hecho_edad_observado():
    c=step(base(),None)
    assert not ruta_documental(c)
    assert ruta_documental(step(c,packet(*request())))==R


def test_t3_observacion_especifica_compatible_resuelve_edad():
    c=step(base(),packet(atom('edad','adulto')))
    assert not ruta_documental(c)
    assert ruta_documental(step(c,packet(atom('edad','menor'))))==R


def test_t4_nuevo_titular_como_hecho_no_requiere_solicitar_titular():
    p=packet(*request(age='adulto',holder='adulto'),
             atom('referencia_titular','otro','solicitud_afirmativa'))
    for e in p['evidencias']:
        if e['dimension']=='titular':e['acto']='observacion'
    c=step(base(),p)
    assert not c['pendientes'] and c['edad']['valor']=='adulto'
    assert not ruta_documental(c)


def test_t4_apoyo_con_hechos_ajenos_no_contamina_objetivo():
    c=step(base(),packet(atom('funcion_documento','apoyo'),
        atom('edad','adulto',sujeto='otro')))
    assert c['edad']['valor']=='menor' and ruta_documental(c)==R


def test_t5_aclaracion_de_operacion_no_rehabilita_rechazo():
    c=step(base(),packet(atom('operacion','renovacion','negacion')))
    c=step(c,packet(atom('operacion','renovacion','aclaracion')))
    assert 'renovacion' in c['rechazadas'] and not ruta_documental(c)
    assert ruta_documental(step(c,packet(atom('operacion','renovacion','solicitud_afirmativa'))))==R


def test_t6_esquema_remoto_rechaza_valor_de_otra_dimension_y_vacio():
    validator=Draft202012Validator(esquema_estricto())
    p=InterpretacionTurno.model_validate(packet(atom('ambito','dni'))).model_dump()
    p['evidencias']=[atom('edad','renovacion')]
    assert list(validator.iter_errors(p))
    p['evidencias']=[]
    assert list(validator.iter_errors(p))


@pytest.mark.parametrize('op', ['renovacion','primera_vez'])
def test_t1_referencia_en_consulta_completa(op):
    c=step(None,packet(*request(op),atom('referencia_titular','actual')))
    assert ruta_documental(c)==('dni_menor_renovacion' if op=='renovacion' else 'dni_menor_primera_vez')


def test_t1_seguimiento_actual_explicito_sin_historia():
    c=step(None,packet(atom('ambito','dni'),atom('tema','seguimiento','solicitud_afirmativa'),
                       atom('referencia_titular','actual')))
    assert ruta_documental(c)=='dni_consulta_estado'


def test_t7_duplicado_no_exige_edad_para_abstenerse():
    p=packet(atom('ambito','dni'),atom('titular','propio'),atom('operacion','duplicado','solicitud_afirmativa'))
    c=step(None,p)
    assert not c['pendientes'] and not ruta_documental(c)


@pytest.mark.parametrize('topic',['coste','plazo','cita','seguimiento'])
def test_t3_tema_no_cancela_contradiccion(topic):
    c=step(base(),packet(atom('edad','adulto')))
    n=step(c,packet(atom('tema',topic,'solicitud_afirmativa')))
    assert 'edad' in n['pendientes'] and not ruta_documental(n)


@pytest.mark.parametrize('act',['observacion','aclaracion'])
def test_t5_rechazo_persiste_incluso_con_hechos_completos(act):
    c=step(base(),packet(atom('operacion','renovacion','negacion')))
    p=packet(*[e for e in request() if e['dimension']!='operacion'],atom('operacion','renovacion',act))
    n=step(c,p)
    assert 'renovacion' in n['rechazadas'] and not ruta_documental(n)


@pytest.mark.parametrize('value',['varios','ambigua'])
def test_t4_varios_titulares_bloquean_aun_con_solicitud_completa(value):
    n=step(base(),packet(*request(),atom('referencia_titular',value)))
    assert 'titular' in n['pendientes'] and not ruta_documental(n)


def test_t1_referencia_contextual_no_se_convierte_en_identificacion_nueva():
    n=step(None,packet(*request(),atom('referencia_titular','actual',origen='referencia_contextual')))
    assert not ruta_documental(n)


def test_t2_no_aplicable_no_desactiva_requisito_real_o_pendiente():
    p=packet(atom('ambito','dni'),atom('titular','propio'),atom('operacion','renovacion','solicitud_afirmativa'))
    p.update(version='2.2',no_aplicables=['edad'])
    assert not ruta_documental(step(None,p))
    c=step(base(),packet(atom('edad','adulto')))
    p=packet(atom('tema','coste','solicitud_afirmativa'))
    p.update(version='2.2',no_aplicables=['edad'])
    assert not ruta_documental(step(c,p))


@pytest.mark.parametrize('extra',[
    {'no_mencionadas':['edad']}, {'no_aplicables':['edad']},
    {'no_mencionadas':['funcion_documento'],'no_aplicables':['funcion_documento']},
])
def test_t6_presencia_incompatible_falla_seguro(extra):
    p=packet(*request());p.update(version='2.2',**extra)
    assert not ruta_documental(step(None,p))


def test_t4_relacion_no_selecciona_objetivo_ni_infiere_edad():
    p=packet(atom('ambito','dni'),atom('relacion','descendiente'),
             atom('operacion','renovacion','solicitud_afirmativa'))
    n=step(None,p)
    assert not n['titular']['valor'] and not n['edad']['valor'] and not ruta_documental(n)


def test_t4_relacion_independiente_del_titular_y_funcion():
    n=step(base(),packet(atom('relacion','descendiente'),atom('funcion_documento','apoyo')))
    assert n['relacion']['valor']=='descendiente' and n['edad']['valor']=='menor'
    assert ruta_documental(n)==R
    revision=n['revision']
    n=step(n,packet(atom('relacion','ascendiente','aclaracion')))
    assert not ruta_documental(n) and 'titular' in n['pendientes']
    assert n['revision']==revision


def test_t4_categoria_no_prueba_identidad_sin_referencia():
    n=step(base(),packet(atom('titular','menor'),atom('tema','coste','solicitud_afirmativa')))
    assert not ruta_documental(n)
    n=step(base(),packet(atom('titular','menor'),atom('referencia_titular','actual'),
                         atom('tema','coste','solicitud_afirmativa')))
    assert ruta_documental(n)==R and n['revision']==0


def test_t7_categoria_titular_y_edad_incompatibles_no_autorizan():
    assert not ruta_documental(step(None,packet(*request(age='menor',holder='adulto'))))


def test_t6_remoto_y_local_coinciden_en_valores_por_dimension():
    from pydantic import ValidationError
    from app.graph.interpretation_contract import VALORES
    validator=Draft202012Validator(esquema_estricto())
    Draft202012Validator.check_schema(esquema_estricto())
    universe=set().union(*VALORES.values())
    for dim,allowed in VALORES.items():
        for value in universe:
            p=packet(atom(dim,value));p.update(no_mencionadas=[],no_aplicables=[])
            remote_ok=not list(validator.iter_errors(p))
            try:InterpretacionTurno.model_validate(p);local_ok=True
            except ValidationError:local_ok=False
            assert remote_ok==local_ok==(value in allowed)


def test_t6_duplicados_y_contradicciones_no_se_normalizan():
    p=packet(*request(),atom('edad','menor'))
    assert not ruta_documental(step(None,p))  # Duplicado exacto rechazado.
    assert not ruta_documental(step(None,packet(*request(),atom('edad','adulto'))))


def test_t7_titular_adulto_y_fuera_de_alcance_no_inventan_rutas():
    for p in (packet(*request(age='adulto',holder='propio')),
              packet(atom('ambito','fuera_alcance'))):
        assert not ruta_documental(step(None,p))


@pytest.mark.parametrize('mode',['conversacion','aislados'])
def test_t7_positivas_y_negativas_en_ambas_modalidades(mode):
    from app.services.interpretation_service import InterpretationService
    from scripts.evaluate_v2_interpretation import evaluar,ProveedorSimulado
    fake=ProveedorSimulado()
    report=evaluar(InterpretationService(client=fake),modalidad='simulada',simulado=fake,
                   modo_turnos=mode,diagnostico=True)
    assert report['satisfactoria'] and report['turnos']==29
    assert report['cobertura_documental']==dict(positivas_esperadas=17,
        positivas_correctamente_autorizadas=17,autorizaciones_totales=17,autorizaciones_incorrectas=0)
    assert report['resumen']['aclaracion_necesaria_atendida']==8
    assert report['resumen']['aclaracion_innecesaria']==0
    assert report['resumen']['abstencion_correcta']==4


def test_t7_no_aprobar_autorizando_cero_con_booleans_inconsistentes():
    from app.services.interpretation_service import InterpretationService
    from scripts.evaluate_v2_interpretation import evaluar,evaluacion_satisfactoria,ProveedorSimulado
    fake=ProveedorSimulado()
    report=evaluar(InterpretationService(client=fake),modalidad='simulada',simulado=fake)
    for row in report['resultados']:row['ruta_obtenida']=''
    assert not evaluacion_satisfactoria(report)
