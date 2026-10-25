from copy import deepcopy
import json

import pytest

from app.graph.canonical_adapter import adaptar_contrato
from app.graph.canonical_delta import normalizar_candidata, normalizar_v22
from app.graph.context_policy import contexto_inicial, ruta_documental, validar_contexto
from app.graph.interpretation_contract import InterpretacionTurno
from app.graph.interpretation_candidate import validar_candidata
from scripts.v2_interpretation_scenarios import packet, request
from scripts.v23_interpretation_scenarios import p, clear, fact, uncertain, objective, operation, support
from scripts.evaluate_canonical_versions import evaluar_version

V='2.3-candidata-1'
R='dni_menor_renovacion'


def step(c,payload,version=V):
    before=deepcopy(c)
    r=adaptar_contrato(c,dict(turno=c['turno']+1 if c else 1,revision=c['revision'] if c else 0),
                       payload,version=version)
    assert c==before and validar_contexto(r.contexto_canonico)
    assert r.ruta==ruta_documental(r.contexto_canonico)
    return r


def base():return step(None,clear()).contexto_canonico


@pytest.mark.parametrize('version',['2.2',V])
@pytest.mark.parametrize('mode',['conversacion','aislados'])
def test_matriz_completa_ejecuta_politica_real(version,mode):
    report=evaluar_version(version,modo=mode,diagnostico=True)
    assert report['satisfactoria'] and report['correctas']==report['turnos']==29
    assert report['positivas_autorizadas']==report['positivas_esperadas']==17
    assert report['autorizaciones_incorrectas']==0


def test_delta_no_inventa_titular_o_edad():
    result=validar_candidata(p(objetivo=objective()))
    delta=normalizar_candidata(result.interpretacion)
    assert delta.objetivo.neutral and delta.objetivo.identificacion=='explicito_unico'
    assert not delta.evidencias
    r=step(None,p(objetivo=objective()))
    assert r.contexto_canonico['objetivo']['estado']=='confirmado'
    assert not r.contexto_canonico['titular']['valor'] and not r.contexto_canonico['edad']['valor']
    assert not r.ruta


def test_objetivo_y_relacion_edad_independientes():
    r=step(None,dict(clear(),relacion=uncertain()))
    assert r.ruta==R and not r.contexto_canonico['pendientes']
    assert r.contexto_canonico['relacion']['estado']=='conflicto'
    assert r.contexto_canonico['objetivo']['valor']=='identificado'
    assert not r.contexto_canonico['titular']['valor']


@pytest.mark.parametrize('topic',['coste','requisitos'])
def test_repreguntas_no_reconfirman_historia(topic):
    c=base()
    r=step(c,p(objetivo=objective('referencia_contextual','actual'),tema=fact(topic,'solicitud_afirmativa')))
    assert r.ruta==R
    for dim in ('objetivo','edad','operacion'):assert r.contexto_canonico[dim]==c[dim]


def test_cambio_referente_invalida_todos_los_dependientes():
    c=base()
    r=step(c,p(objetivo=objective(ref='otro')))
    assert r.contexto_canonico['revision']==c['revision']+1 and not r.ruta
    for dim in ('edad','operacion','dni_previo','funcion_documento'):
        assert not r.contexto_canonico[dim]['valor']
    assert 'relacion' not in r.contexto_canonico


def test_nuevo_referente_no_puede_tomar_edad_contextual_anterior():
    r=step(base(),p(objetivo=objective(ref='otro'),edad=fact('menor',origin='referencia_contextual'),
                    operaciones=operation()))
    assert not r.ruta and 'edad' in r.contexto_canonico['pendientes']


def test_cambio_explicito_adulto_abstiene_sin_corpus():
    r=step(base(),clear(age='adulto',relation='ascendiente',ref='otro'))
    assert not r.contexto_canonico['pendientes'] and not r.ruta
    assert r.contexto_canonico['edad']['valor']=='adulto'


@pytest.mark.parametrize('kind',['multiple','ambiguo'])
def test_varios_objetivos_no_autorizan_ni_heredan(kind):
    r=step(base(),p(objetivo=objective(kind)))
    assert not r.ruta and 'titular' in r.contexto_canonico['pendientes']
    assert not r.contexto_canonico['edad']['valor']
    n=step(r.contexto_canonico,p(objetivo=objective('referencia_contextual','actual')))
    assert not n.ruta


def test_referencia_contextual_sin_objetivo_previo_no_autoriza():
    r=step(None,p(objetivo=objective('referencia_contextual','actual'),ambito=fact('dni'),
                  edad=fact('menor'),operaciones=operation()))
    assert not r.ruta and 'titular' in r.contexto_canonico['pendientes']


def test_rechazo_solo_se_rehabilita_por_solicitud_nueva_explicita():
    c=step(base(),p(operaciones=operation(act='negacion'))).contexto_canonico
    for payload in [p(relacion=fact('descendiente','aclaracion')),
                    p(operaciones=operation(act='observacion')),
                    p(operaciones=operation(act='aclaracion')),
                    p(operaciones=operation(origin='referencia_contextual'))]:
        r=step(c,payload)
        assert not r.ruta and 'renovacion' in r.contexto_canonico['rechazadas']
        c=r.contexto_canonico
    assert step(c,p(operaciones=operation())).ruta==R


def test_aclaracion_sin_aceptacion_anterior_no_inicia_operacion():
    payload=clear();payload['operaciones']=operation(act='aclaracion')
    assert not step(None,payload).ruta


def test_afirmacion_y_negacion_mismo_turno_no_se_cancelan():
    r=step(base(),p(operaciones={'renovacion':{'solicitud':support(),'negacion':support()}}))
    assert not r.ruta and 'renovacion' in r.contexto_canonico['rechazadas']


@pytest.mark.parametrize('topic',['coste','cita','requisitos','seguimiento'])
def test_contradiccion_edad_no_se_resuelve_con_tema(topic):
    c=step(base(),p(edad=fact('adulto'))).contexto_canonico
    assert 'edad' in c['pendientes']
    assert not step(c,p(tema=fact(topic,'solicitud_afirmativa'))).ruta
    assert not step(c,p(edad=fact('menor',origin='referencia_contextual'))).ruta
    assert step(c,p(edad=fact('menor','aclaracion'))).ruta==R


def test_apoyo_no_transfiere_edad_del_acompanante():
    c=base()
    r=step(c,p(funcion_documento=fact('apoyo'),edad=fact('adulto',subject='acompanante')))
    assert r.ruta==R and r.contexto_canonico['edad']==c['edad']


def test_operacion_de_acompanante_no_inicia_procedimiento_del_objetivo():
    payload=clear();payload['operaciones']=operation(subject='acompanante')
    assert not step(None,payload).ruta


def test_relacion_sola_no_identifica_objetivo_o_edad():
    r=step(None,p(ambito=fact('dni'),relacion=fact('descendiente'),operaciones=operation()))
    assert not r.ruta
    assert not r.contexto_canonico['objetivo']['valor'] and not r.contexto_canonico['edad']['valor']


def test_tenencia_persiste_y_bloquea_incompatibilidad():
    c=step(None,dict(clear('primera_vez'),dni_previo=fact('no'))).contexto_canonico
    r=step(c,p(operaciones=operation()))
    assert not r.ruta and 'dni_previo' in r.contexto_canonico['pendientes']
    assert step(r.contexto_canonico,p(dni_previo=fact('si','aclaracion'))).ruta==R


def test_migracion_legacy_no_reconfirma_objetivo():
    legacy=step(None,packet(*request()),version='2.2').contexto_canonico
    old=deepcopy(legacy['titular'])
    r=step(legacy,p(objetivo=objective('referencia_contextual','actual'),tema=fact('coste','solicitud_afirmativa')))
    assert r.ruta==R
    migrated=r.contexto_canonico['objetivo']
    assert migrated==dict(old,valor='identificado')


@pytest.mark.parametrize('payload',[None,{},'bad-json',{'version':'2.2'},p(nombre='SENSITIVE_SENTINEL')])
def test_fallo_no_reutiliza_ruta_historica(payload):
    r=step(base(),payload)
    assert r.codigo=='contrato_invalido' and not r.ruta
    assert 'SENSITIVE_SENTINEL' not in json.dumps(r.traza)


@pytest.mark.parametrize('meta',[dict(turno=1,revision=0),dict(turno=2,revision=1),dict(turno=True,revision=0)])
def test_metadatos_obsoletos_bloquean(meta):
    r=adaptar_contrato(base(),meta,clear(),version=V)
    assert r.codigo=='vigencia_invalida' and not r.ruta


def test_version_no_se_adivina():
    r=adaptar_contrato(None,dict(turno=1,revision=0),clear(),version='2.2')
    assert r.codigo=='contrato_invalido' and not r.ruta
    r=adaptar_contrato(None,dict(turno=1,revision=0),packet(*request()),version=V)
    assert r.codigo=='contrato_invalido' and not r.ruta


def test_trazas_no_historial_y_sin_identidades():
    r=step(None,clear())
    assert 'historial' not in r.contexto_canonico and 'traza' not in r.contexto_canonico
    assert set(r.traza['campos'])=={'objetivo','titular','edad','operacion','dni_previo','funcion_documento','relacion'}
    assert r.traza['campos']['objetivo']['despues']['turno']==1
    assert r.traza['revision']==0


def test_ambas_entradas_usan_unica_transicion(monkeypatch):
    import app.graph.canonical_adapter as module
    original=module.transicionar_delta
    calls=[]
    def spy(c,d):calls.append(d);return original(c,d)
    monkeypatch.setattr(module,'transicionar_delta',spy)
    assert step(None,clear()).ruta==R
    assert step(None,packet(*request()),version='2.2').ruta==R
    assert len(calls)==2 and all(type(d).__name__=='DeltaCanonico' for d in calls)


def test_no_hay_downgrade_silencioso_de_objetivo_a_parentesco():
    r=step(base(),packet(*request()),version='2.2')
    assert r.codigo=='version_estado_incompatible' and not r.ruta
    assert r.contexto_canonico['objetivo']['valor']=='identificado'


def test_fallo_de_politica_no_expone_excepcion_o_ruta_historica(monkeypatch,caplog):
    import app.graph.canonical_adapter as module
    def broken(*args):raise RuntimeError('SENSITIVE_EXCEPTION')
    monkeypatch.setattr(module,'transicionar_delta',broken)
    r=step(base(),p(tema=fact('coste','solicitud_afirmativa')))
    assert r.codigo=='adaptacion_invalida' and not r.ruta
    assert 'SENSITIVE_EXCEPTION' not in json.dumps(r.traza)+caplog.text


def test_relacion_incierta_no_pierde_vigencia_del_objetivo():
    c=base()
    r=step(c,p(relacion=uncertain(),tema=fact('coste','solicitud_afirmativa')))
    assert r.ruta==R and r.contexto_canonico['objetivo']==c['objetivo']
    assert r.contexto_canonico['relacion']['estado']=='conflicto'


def test_incertidumbre_de_edad_material_bloquea_sin_borrar_objetivo():
    c=base()
    r=step(c,p(edad=uncertain()))
    assert not r.ruta and 'edad' in r.contexto_canonico['pendientes']
    assert r.contexto_canonico['objetivo']==c['objetivo']


def test_contexto_corrupto_no_usa_campos_personales():
    c=base();c['nombre']='SENSITIVE_NAME'
    r=adaptar_contrato(c,dict(turno=2,revision=0),clear(),version=V)
    assert r.codigo=='contexto_invalido' and not r.ruta
    assert 'SENSITIVE_NAME' not in json.dumps(r.traza)


def test_normalizadores_conservan_actos_y_procedencia_sin_aceptacion_implicita():
    delta=normalizar_candidata(validar_candidata(p(operaciones={'renovacion':{
        'negacion':support(),'observacion':support(origin='referencia_contextual')}})).interpretacion)
    assert {e.acto for e in delta.evidencias}=={'negacion','observacion'}
    assert any(e.origen=='referencia_contextual' for e in delta.evidencias)
    legacy=normalizar_v22(InterpretacionTurno.model_validate(packet(*request())))
    assert not legacy.objetivo.neutral
    assert any(e.dimension=='titular' and e.valor=='descendiente' for e in legacy.evidencias)


def test_contradiccion_relacional_explicita_no_se_descarta_como_incertidumbre():
    r=step(base(),p(relacion=uncertain('contradictorio')))
    assert not r.ruta and 'titular' in r.contexto_canonico['pendientes']


def test_traza_delta_conserva_fuente_y_no_guarda_respuesta_cruda():
    r=step(base(),p(objetivo=objective('referencia_contextual','actual'),
                    tema=fact('coste','solicitud_afirmativa')))
    assert r.traza['delta']['objetivo']['identificacion']=='referencia_contextual'
    assert r.traza['delta']['evidencias'][0]['origen']=='explicito_turno'
    assert not {'pregunta','historial','output_text','api_key'} & r.traza.keys()


def test_objetivo_corrupto_no_pasa_puerta_documental_sin_pendiente():
    c=base()
    c['objetivo']['estado']='desconocido';c['objetivo']['valor']=''
    c['objetivo']['origen']='ausente'
    assert not validar_contexto(c) and not ruta_documental(c)


def test_aclaracion_no_cambia_una_operacion_confirmada_por_otra():
    c=step(None,clear('primera_vez')).contexto_canonico
    r=step(c,p(operaciones=operation('renovacion',act='aclaracion')))
    assert not r.ruta and 'operacion' in r.contexto_canonico['pendientes']
    assert step(r.contexto_canonico,p(operaciones=operation('renovacion'))).ruta==R


def test_delta_legacy_identifica_solo_desde_rol_explicito_no_edad_o_parentesco():
    legacy=normalizar_v22(InterpretacionTurno.model_validate(packet(*request())))
    assert legacy.objetivo.identificacion=='explicito_unico'
    from scripts.v2_interpretation_scenarios import atom
    relationship_only=normalizar_v22(InterpretacionTurno.model_validate(packet(
        atom('relacion','descendiente'),atom('edad','menor'))))
    assert relationship_only.objetivo.identificacion=='no_mencionado'


@pytest.mark.parametrize('version',['2.2',V])
def test_cli_ejecuta_politica_real_y_exporta_categorias(version,tmp_path,capsys):
    from scripts.evaluate_canonical_versions import main
    path=tmp_path/'canonical.json'
    assert main(['--version',version,'--modo','aislados','--diagnostico','--output',str(path)])==0
    report=json.loads(path.read_text())
    assert report==json.loads(capsys.readouterr().out)
    assert report['positivas_autorizadas']==17 and report['autorizaciones_incorrectas']==0
