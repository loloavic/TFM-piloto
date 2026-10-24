from openai import OpenAI

from app.core.config import settings


class LLMService:
    def __init__(self):
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY no está configurada.")

        self.client = OpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            timeout=settings.provider_timeout_seconds, max_retries=0
        )
        self.model = settings.openai_model

    def generar_respuesta(self, pregunta: str) -> str:
        response = self.client.responses.create(
            model=self.model,
            input=pregunta,
            max_output_tokens=300,
        )

        return response.output_text