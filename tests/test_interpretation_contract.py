"""Contrato V2.1: proveedor inexistente, casos sintéticos categóricos."""
from copy import deepcopy
import json

import pytest
from pydantic import ValidationError

from app.graph.context_policy import OPERACIONES, TEMAS, VALORES
from app.graph.interpretation_contract import (
    EntradaInterpretacion, InterpretacionTurno, VALORES as VOCABULARIO,
    validar_interpretacion,
)

META = {'turno': 1, 'revision': 0}


def evidencia(dimension, valor, acto='observacion', **extra):
    return dict(dimension=dimension, valor=valor, acto=acto,
                origen='explicito_turno', sujeto='objetivo', **extra)


def completa():
    return dict(version='2.1', evidencias=[
        evidencia('ambito', 'dni'), evidencia('titular', 'descendiente'),
        evidencia('edad', 'menor'),
        evidencia('operacion', 'renovacion', 'solicitud_afirmativa'),
        evidencia('tema', 'requisitos'), evidencia('dni_previo', 'si'),
    ], faltantes=[], contradicciones=[])


def resultado(data):
    return validar_interpretacion(META, data)


def test_completa_dict_y_json_sin_autorizacion():
    for payload in (completa(), json.dumps(completa())):
        r = resultado(payload)
        assert r.estado == 'suficiente' and not r.motivos
        assert r.entrada.turno == 1
        assert not hasattr(r, 'ruta_documental')
        assert 'confianza' not in InterpretacionTurno.model_json_schema()['properties']


def test_vocabulario_existente():
    assert VOCABULARIO['operacion'] == OPERACIONES | {'desconocido'}
    assert VOCABULARIO['tema'] == TEMAS
    assert VOCABULARIO['titular'] == VALORES['titular'] | {'desconocido'}


@pytest.mark.parametrize('dimension', ['ambito', 'titular', 'edad', 'operacion'])
def test_incompleta(dimension):
    p = completa()
    p['evidencias'] = [e for e in p['evidencias'] if e['dimension'] != dimension]
    r = resultado(p)
    assert r.estado == 'requiere_aclaracion' and dimension in r.motivos


@pytest.mark.parametrize('dimension,valor', [
    ('edad', 'adulto'), ('operacion', 'primera_vez'), ('ambito', 'fuera_alcance'),
    ('titular', 'propio'), ('dni_previo', 'no'),
])
def test_contradicciones_no_declaradas(dimension, valor):
    p = completa()
    p['evidencias'].append(evidencia(dimension, valor))
    assert resultado(p).estado == 'requiere_aclaracion'
    assert 'contradiccion' in resultado(p).motivos


@pytest.mark.parametrize('op,previo', [('primera_vez', 'si'), ('renovacion', 'no'), ('duplicado', 'no')])
def test_incompatibilidad_procedimiento_tenencia(op, previo):
    p = completa()
    p['evidencias'][3]['valor'] = op
    p['evidencias'][5]['valor'] = previo
    assert 'dni_previo' in resultado(p).motivos


@pytest.mark.parametrize('acto', ['negacion', 'observacion'])
def test_no_convierte_negacion_u_observacion_en_solicitud(acto):
    p = completa()
    p['evidencias'][3]['acto'] = acto
    r = resultado(p)
    assert r.estado == 'requiere_aclaracion' and 'operacion' in r.motivos


def test_operacion_afirmada_y_negada_no_se_resuelve_por_orden():
    p = completa()
    p['evidencias'].append(evidencia('operacion', 'renovacion', 'negacion'))
    assert 'contradiccion' in resultado(p).motivos
    p['evidencias'].reverse()
    assert 'contradiccion' in resultado(p).motivos


def test_negacion_otra_operacion_no_es_contradiccion():
    p = completa()
    p['evidencias'].append(evidencia('operacion', 'primera_vez', 'negacion'))
    assert resultado(p).estado == 'suficiente'


def test_aclaracion_explicita_y_referencia_no_equivalen():
    p = completa()
    p['evidencias'][3]['acto'] = 'aclaracion'
    assert resultado(p).estado == 'suficiente'
    p['evidencias'][3]['origen'] = 'referencia_contextual'
    assert resultado(p).estado == 'requiere_aclaracion'


@pytest.mark.parametrize('sujeto', ['otro', 'no_resuelto'])
def test_no_mezcla_titulares(sujeto):
    p = completa()
    other = evidencia('edad', 'adulto')
    other['sujeto'] = sujeto
    p['evidencias'].append(other)
    assert 'titular' in resultado(p).motivos


@pytest.mark.parametrize('valor', ['otro', 'varios', 'ambigua'])
def test_referencias_materiales(valor):
    p = completa()
    p['evidencias'].append(evidencia('referencia_titular', valor))
    assert 'referencia' in resultado(p).motivos


@pytest.mark.parametrize('field', ['faltantes', 'contradicciones'])
def test_duda_declarada_no_se_ignora(field):
    p = completa()
    p[field] = ['documento']
    assert resultado(p).estado == 'requiere_aclaracion'


@pytest.mark.parametrize('mutation', [
    lambda p: p.update(confianza=1.0),
    lambda p: p.update(ruta_documental='dni_menor_renovacion'),
    lambda p: p.update(version=2.1),
    lambda p: p.pop('faltantes'),
    lambda p: p.update(evidencias=None),
    lambda p: p.update(faltantes='edad'),
    lambda p: p.update(contradicciones=['error libre']),
    lambda p: p['evidencias'][0].update(valor='pasaporte'),
    lambda p: p['evidencias'][0].update(valor='menor'),
    lambda p: p['evidencias'][0].update(valor=True),
    lambda p: p['evidencias'][0].update(nombre='PERSONA_SINTETICA'),
    lambda p: p['evidencias'][0].update(origen='historial'),
    lambda p: p['evidencias'][0].update(acto='probable'),
    lambda p: p['evidencias'].append(deepcopy(p['evidencias'][0])),
    lambda p: p.update(evidencias=p['evidencias'] * 6),
])
def test_malformadas_sin_filtracion(mutation):
    p = completa()
    mutation(p)
    r = resultado(p)
    assert r.estado == 'insuficiente_o_invalida'
    assert r.interpretacion is None and r.entrada is None
    assert 'PERSONA_SINTETICA' not in repr(r)


@pytest.mark.parametrize('payload', [None, [], 1, True, '{', 'null',
    '```json\n{}\n```', '{"version":"2.1","version":"2.1"}', ' ' * 16385])
def test_salida_inesperada(payload):
    assert resultado(payload).estado == 'insuficiente_o_invalida'


@pytest.mark.parametrize('meta', [None, {}, {'turno': True, 'revision': 0},
    {'turno': '1', 'revision': 0}, {'turno': 0, 'revision': 0},
    {'turno': 1, 'revision': -1}, {'turno': 1, 'revision': 0, 'nombre': 'X'}])
def test_metadatos_internos_estrictos(meta):
    assert validar_interpretacion(meta, completa()).estado == 'insuficiente_o_invalida'


def test_modelo_invalido_no_puede_saltar_frontera():
    p = InterpretacionTurno.model_construct(**completa())
    assert resultado(p).estado == 'insuficiente_o_invalida'
    with pytest.raises(ValidationError):
        EntradaInterpretacion(turno=True, revision=0)


def test_seguimiento_y_vacio():
    p = dict(version='2.1', evidencias=[evidencia('ambito', 'dni'),
             evidencia('tema', 'seguimiento', 'solicitud_afirmativa')],
             faltantes=[], contradicciones=[])
    assert resultado(p).estado == 'suficiente'
    p['evidencias'] = []
    assert resultado(p).estado == 'insuficiente_o_invalida'


def test_validacion_no_muta_entrada():
    p = completa()
    before = deepcopy(p)
    resultado(p)
    assert p == before
