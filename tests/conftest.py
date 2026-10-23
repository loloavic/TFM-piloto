import pytest
from pydantic import SecretStr

from app.api import routes
from app.core.config import settings
from app.services import evaluation_service, log_service
from app.services.rag_service import RAGService


@pytest.fixture(autouse=True)
def entorno_aislado(tmp_path, monkeypatch):
    """No escribir consultas ni métricas en el almacenamiento de la aplicación."""
    log = tmp_path / 'metricas.csv'
    monkeypatch.setattr(log_service, 'LOG_PATH', log)
    monkeypatch.setattr(evaluation_service, 'LOG_PATH', log)
    monkeypatch.setattr(settings, 'internal_api_token', SecretStr('test-admin-only'))
    service = RAGService()
    monkeypatch.setattr(routes, 'rag', service)
    yield service
    service.sessions.close()
