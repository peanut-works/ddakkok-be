import logging

from app.ai.base import AIProvider, ChatMessage
from app.ai.mock import MockAIProvider

logger = logging.getLogger(__name__)


class FallbackAIProvider(AIProvider):
    """primary provider 호출 실패 시 MockAIProvider로 자동 전환하는 래퍼.

    GMS key 미설정, OpenAI 할당량 초과, 네트워크 오류, timeout 등 모든 예외를
    잡아 mock 응답으로 대체한다. 시연 환경에서 API key 없이도 동작 가능.

    실패 시 아래 두 곳에 기록한다:
      - 콘솔 WARNING (기존)
      - log/ai_failures.log 파일 (AI-08 추가)
    """

    def __init__(self, primary: AIProvider) -> None:
        self._primary = primary
        self._fallback = MockAIProvider()
        self._provider_name = type(primary).__name__

    async def chat_complete(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.3,
    ) -> str:
        try:
            return await self._primary.chat_complete(messages, temperature)
        except Exception as e:
            self._log_failure("chat_complete", e)
            return await self._fallback.chat_complete(messages, temperature)

    async def function_call(
        self,
        messages: list[ChatMessage],
        tools: list[dict],
        tool_choice: str = "auto",
    ) -> dict:
        try:
            return await self._primary.function_call(messages, tools, tool_choice)
        except Exception as e:
            self._log_failure("function_call", e)
            return await self._fallback.function_call(messages, tools, tool_choice)

    def _log_failure(self, method: str, exc: Exception) -> None:
        """실패를 콘솔과 log/ai_failures.log 파일에 동시에 기록한다."""
        msg = (
            f"[AI FALLBACK] provider={self._provider_name} "
            f"method={method} "
            f"error={type(exc).__name__}: {exc}"
        )
        logger.warning(msg)
        _file_logger.warning(msg)


# ── 파일 핸들러 (log/ai_failures.log) ────────────────────────────────────────

def _build_file_logger() -> logging.Logger:
    """AI 실패 전용 파일 로거. 모듈 로드 시 1회 초기화."""
    import os
    from logging.handlers import RotatingFileHandler

    log_dir = "log"
    os.makedirs(log_dir, exist_ok=True)

    file_logger = logging.getLogger("ai.failures")
    if file_logger.handlers:          # 중복 핸들러 방지
        return file_logger

    file_logger.setLevel(logging.WARNING)
    handler = RotatingFileHandler(
        filename=os.path.join(log_dir, "ai_failures.log"),
        maxBytes=1 * 1024 * 1024,     # 1 MB
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )
    file_logger.addHandler(handler)
    file_logger.propagate = False     # 루트 로거 중복 출력 방지
    return file_logger


_file_logger = _build_file_logger()
