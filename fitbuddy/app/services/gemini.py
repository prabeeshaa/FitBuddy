import logging

from ..config import Settings

logger = logging.getLogger(__name__)


class GeminiServiceError(RuntimeError):
    """Raised when a configured Gemini request cannot be completed."""


class GeminiService:
    """Small adapter around Google's current google-genai SDK."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = None

    def _get_client(self):
        if not self.settings.gemini_configured:
            raise GeminiServiceError("GEMINI_API_KEY is not configured")
        if self._client is None:
            try:
                from google import genai

                self._client = genai.Client(
                    api_key=self.settings.gemini_api_key,
                    http_options={"timeout": int(self.settings.gemini_timeout_seconds * 1000)},
                )
            except Exception as exc:  # pragma: no cover - depends on optional SDK/runtime
                raise GeminiServiceError("The google-genai SDK could not be initialized") from exc
        return self._client

    def generate_text(self, prompt: str, model: str) -> str:
        try:
            response = self._get_client().models.generate_content(model=model, contents=prompt)
            text = getattr(response, "text", None)
            if not text or not text.strip():
                raise GeminiServiceError("Gemini returned an empty response")
            return text.strip()
        except GeminiServiceError:
            raise
        except Exception as exc:  # pragma: no cover - network/provider dependent
            logger.exception("Gemini request failed")
            raise GeminiServiceError("Gemini request failed") from exc

