"""AI 응답 캐싱 — 같은 입력에 대해 AI를 반복 호출하지 않는다.

파이프라인 위치: any AIProvider → [CachedAIProvider] ← 요청

동작 방식:
  1. 입력(messages + temperature/tools)을 SHA-256으로 해시
  2. 캐시 히트 → 저장된 응답 즉시 반환 (AI 호출 없음)
  3. 캐시 미스 → primary 호출 후 결과 저장
  4. maxsize 초과 시 가장 오래된 항목부터 제거 (LRU)

적용 대상:
  - mock: 캐싱 불필요 (즉시 반환, 비용 없음) — factory에서 미적용
  - openai / gms: 자동 활성화 — 중복 API 호출 차단
"""

import hashlib
import json
import logging
from collections import OrderedDict

from app.ai.base import AIProvider, ChatMessage

logger = logging.getLogger(__name__)


# ── Hash ──────────────────────────────────────────────────────────────────────

def _make_key(*parts: object) -> str:
    """입력값을 JSON 직렬화 후 SHA-256 해시로 변환한다."""
    payload = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


# ── Cache ─────────────────────────────────────────────────────────────────────

class CachedAIProvider(AIProvider):
    """AI 응답을 in-memory LRU 캐시로 저장하는 래퍼.

    같은 messages + temperature/tools 조합이면 API 호출 없이 캐시 응답 반환.
    컨테이너 재시작 시 캐시 초기화 (in-memory).

    Args:
        primary : 실제 AI 호출을 수행할 provider (FallbackAIProvider 권장)
        maxsize : 최대 캐시 항목 수. 초과 시 LRU 제거. (기본값 256)
    """

    def __init__(self, primary: AIProvider, maxsize: int = 256) -> None:
        self._primary = primary
        self._maxsize = maxsize
        self._chat_cache: OrderedDict[str, str] = OrderedDict()
        self._fn_cache: OrderedDict[str, dict] = OrderedDict()

    # ── Public ────────────────────────────────────────────────────────────────

    async def chat_complete(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.3,
    ) -> str:
        key = _make_key([m.model_dump() for m in messages], temperature)

        if key in self._chat_cache:
            self._chat_cache.move_to_end(key)
            logger.debug("cache hit  [chat] %s…", key[:8])
            return self._chat_cache[key]

        logger.debug("cache miss [chat] %s…", key[:8])
        result = await self._primary.chat_complete(messages, temperature)
        self._put(self._chat_cache, key, result)
        return result

    async def function_call(
        self,
        messages: list[ChatMessage],
        tools: list[dict],
        tool_choice: str = "auto",
    ) -> dict:
        key = _make_key([m.model_dump() for m in messages], tools, str(tool_choice))

        if key in self._fn_cache:
            self._fn_cache.move_to_end(key)
            logger.debug("cache hit  [fn]   %s…", key[:8])
            return self._fn_cache[key]

        logger.debug("cache miss [fn]   %s…", key[:8])
        result = await self._primary.function_call(messages, tools, tool_choice)
        self._put(self._fn_cache, key, result)
        return result

    # ── Stats (디버그·테스트용) ────────────────────────────────────────────────

    @property
    def chat_cache_size(self) -> int:
        return len(self._chat_cache)

    @property
    def fn_cache_size(self) -> int:
        return len(self._fn_cache)

    def clear(self) -> None:
        """캐시 전체 초기화."""
        self._chat_cache.clear()
        self._fn_cache.clear()
        logger.debug("cache cleared")

    # ── Internal ──────────────────────────────────────────────────────────────

    def _put(self, cache: "OrderedDict[str, object]", key: str, value: object) -> None:
        """캐시에 항목 추가. maxsize 초과 시 가장 오래된 항목 제거."""
        if len(cache) >= self._maxsize:
            evicted_key, _ = cache.popitem(last=False)
            logger.debug("cache evict %s…", evicted_key[:8])
        cache[key] = value  # type: ignore[assignment]
