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
