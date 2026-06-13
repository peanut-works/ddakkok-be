"""AI provider 공용 재시도 유틸.

Fallback 래퍼들이 mock으로 전환하기 전에 일시적 장애(네트워크·timeout·5xx 등)를
짧은 backoff 후 1회 더 시도하도록 한다. 모든 시도가 실패하면 마지막 예외를 그대로
raise해 caller(Fallback 래퍼)가 mock 응답으로 전환하게 한다.

성공 시에는 추가 호출이 없으므로 GMS 가이드의 "불필요한 호출 자제"에 위배되지 않는다.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

DEFAULT_RETRIES = 1  # 최초 실패 후 추가 시도 횟수
DEFAULT_BACKOFF = 0.5  # 재시도 전 대기 시간(초)


async def retry_async[T](
    operation: Callable[[], Awaitable[T]],
    *,
    retries: int = DEFAULT_RETRIES,
    backoff: float = DEFAULT_BACKOFF,
    label: str = "",
) -> T:
    """operation()을 실행하고, 실패 시 backoff 후 retries회까지 재시도한다.

    Args:
        operation: 매 시도마다 새 awaitable을 반환하는 콜러블.
        retries:   최초 실패 후 추가 시도 횟수 (기본 1회).
        backoff:   재시도 전 대기 시간(초).
        label:     로그 식별용 라벨.

    모든 시도가 실패하면 마지막 예외를 raise한다.
    """
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return await operation()
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                logger.warning(
                    "[AI RETRY] %s 시도 %d/%d 실패 (%s) — %.1fs 후 재시도",
                    label or "operation",
                    attempt + 1,
                    retries + 1,
                    type(exc).__name__,
                    backoff,
                )
                await asyncio.sleep(backoff)
    assert last_exc is not None  # 루프가 최소 1회 실행되므로 항상 설정됨
    raise last_exc
