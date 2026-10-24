import os

os.environ.setdefault('GRADIO_ANALYTICS_ENABLED', 'False')

from app import ui
from app.services.rag_service import RAGService


def test_gradio_conserva_credencial_en_estado_y_borra_al_reiniciar(monkeypatch):
    service = RAGService()
    monkeypatch.setattr(ui, 'rag', service)
    try:
        initial = ui.generar_session_id()
        result = ui.responder_consulta('Necesito renovar mi pasaporte. DNI 12345678', [], initial)
        state = result[2]
        assert state['token']
        assert state['token'] not in str(result[1]) + str(result[4])
        assert '12345678' not in str(result[1])
        assert list(service.grafo.checkpointer.list(None))
        reset = ui.nueva_conversacion(state)
        assert reset[1]['id'] != state['id']
        assert not list(service.grafo.checkpointer.list(None))
        assert not service.grafo.checkpointer.writes and not service.grafo.checkpointer.blobs
    finally:
        service.sessions.close()


def test_gradio_no_acepta_id_ajeno_sin_credencial(monkeypatch):
    service = RAGService()
    monkeypatch.setattr(ui, 'rag', service)
    try:
        owner = ui.responder_consulta('Necesito renovar mi pasaporte.', [], ui.generar_session_id())
        sid = owner[2]['id']
        rejected = ui.responder_consulta('Otra consulta pasaporte', [], {'id': sid, 'token': None})
        assert 'Consulta no completada' in rejected[4]
        assert 'SesionNoAutorizada' not in str(rejected)
        ui.eliminar_estado_sesion(owner[2])
        assert not list(service.grafo.checkpointer.list(None))
    finally:
        service.sessions.close()


def test_reinicio_ocupado_no_afirma_borrado(monkeypatch):
    import pytest
    from unittest.mock import Mock
    from app.services.session_service import SesionOcupada
    store = Mock()
    store.delete.side_effect = SesionOcupada()
    monkeypatch.setattr(ui, 'rag', Mock(sessions=store))
    with pytest.raises(ui.gr.Error):
        ui.nueva_conversacion({'id': 'ficticio', 'token': 'credencial-ficticia'})


def test_cola_gradio_permite_sesiones_independientes():
    functions = [fn for fn in ui.demo.fns.values() if fn.fn is ui.responder_consulta]
    assert functions
    assert all(fn.concurrency_limit == 8 and fn.concurrency_id == 'consultas' for fn in functions)
