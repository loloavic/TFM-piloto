import csv
import pytest
from app.services import log_service
from tests.test_adult_dni import motor

@pytest.mark.parametrize('intent', ['dni_menor_primera_vez','dni_menor_renovacion',
    'dni_consulta_estado','dni_amarillo_a_azul_primera_vez','dni_adulto_renovacion',
    'dni_adulto_rectificacion','general','fuera_alcance'])
def test_metricas_conservan_intencion(intent,tmp_path,monkeypatch):
    path=tmp_path/'metrics.csv'
    monkeypatch.setattr(log_service,'LOG_PATH',path)
    log_service.registrar_consulta('','',''+intent,'ok',[])
    with path.open(encoding='utf-8') as f: row=next(csv.DictReader(f))
    assert row['intencion']==intent
    assert row['pregunta']==row['respuesta']=='' and row['fuentes']=='[]'

@pytest.mark.parametrize('status,expected', [('ok','ok'),('observada: control','observada'),
    ('abstencion_documental: fuente#regla','abstencion_documental'),('desconocido','observada')])
def test_metricas_verificacion(status,expected,tmp_path,monkeypatch):
    path=tmp_path/'metrics.csv';monkeypatch.setattr(log_service,'LOG_PATH',path)
    log_service.registrar_consulta('','','general',status,[])
    with path.open(encoding='utf-8') as f: row=next(csv.DictReader(f))
    assert row['verificacion']==expected


def test_resumen_y_contrato_api_conservan_categorias(tmp_path,monkeypatch):
    from app.services.evaluation_service import generar_resumen_evaluacion
    from app.models import EvaluacionResumenResponse
    path=tmp_path/'metrics.csv';monkeypatch.setattr(log_service,'LOG_PATH',path)
    log_service.registrar_consulta('','','dni_adulto_renovacion','abstencion_documental: regla',[])
    log_service.registrar_consulta('','','dni_adulto_rectificacion','observada: control',[])
    summary=generar_resumen_evaluacion(path)
    assert summary['total_consultas']==2 and summary['consultas_observadas']==1
    assert set(summary['resumen_verificacion']['verificacion'])=={'observada','abstencion_documental'}
    # Mismo esquema; las categorías son cadenas abiertas en API.
    response=EvaluacionResumenResponse(total_consultas=2,consultas_fuera_alcance=0,
        consultas_observadas=1,resumen_intenciones=[{'categoria':'dni_adulto_renovacion','cantidad':1}],
        resumen_verificacion=[{'categoria':'abstencion_documental','cantidad':1}])
    assert response.resumen_verificacion[0].categoria=='abstencion_documental'


def test_ui_explica_ok_sin_cambiar_api(motor,monkeypatch):
    from app import ui
    service,_,_=motor
    monkeypatch.setattr(ui,'rag',service)
    result=ui.responder_consulta('Soy adulto y quiero renovar mi DNI. ¿Cuánto demora?',[],ui.generar_session_id())
    assert 'ok' in result[4] and 'no certifica exactitud factual universal' in result[4]
