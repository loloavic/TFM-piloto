import sys

import pytest
from pydantic import SecretStr

from app.api import routes
from app.core.config import settings
from app.services import evaluation_service, log_service
from app.services.rag_service import RAGService


@pytest.fixture(autouse=True)
def entorno_aislado(tmp_path, monkeypatch, request):
    """No escribir consultas ni métricas en el almacenamiento de la aplicación."""
    # Se monta el demo global en una app ASGI nueva por prueba. Gradio enlaza
    # su cola a la primera app que recibe queue/join y no borra ese enlace al
    # cerrar TestClient. No reutilizar el StateHolder de otra prueba/aplicación.
    ui = sys.modules.get('app.ui')
    if ui is not None:
        ui.demo._queue.set_server_app(None)
    if not request.node.get_closest_marker('integration'):
        # El docstore local del usuario no forma parte de las pruebas unitarias.
        monkeypatch.setattr('app.graph.dni_graph.recuperar_reglas_exactas', lambda *args, **kwargs: [])
    log = tmp_path / 'metricas.csv'
    monkeypatch.setattr(log_service, 'LOG_PATH', log)
    monkeypatch.setattr(evaluation_service, 'LOG_PATH', log)
    monkeypatch.setattr(settings, 'internal_api_token', SecretStr('test-admin-only'))
    service = RAGService()
    monkeypatch.setattr(routes, 'rag', service)
    yield service
    service.sessions.close()
    if ui is not None:
        ui.demo._queue.set_server_app(None)
