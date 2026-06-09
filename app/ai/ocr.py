"""OCR 프로바이더 인터페이스 및 구현체.

구현체:
    MockOCRProvider   — 시나리오 키 기반 고정 텍스트 반환 (외부 API 없음)
    ClovaOCRProvider  — Naver CLOVA OCR API 호출
    FallbackOCRProvider — primary 실패 시 mock으로 자동 전환
"""

import base64
import logging
import uuid
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Any

import httpx

from app.ai.ocr_mock_data import DEFAULT_OCR_SCENARIO, MOCK_OCR_RESULTS

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 15.0  # 초. AI provider와 통일


class OCRProvider(ABC):
    """이미지에서 텍스트를 추출하는 OCR 인터페이스.

    실제 구현체: ClovaOCRProvider
    Mock 구현체: MockOCRProvider
    """

    @abstractmethod
    async def extract_text(self, image: bytes) -> str:
        """이미지 바이트를 받아 추출된 원시 텍스트를 반환한다."""


# ---------------------------------------------------------------------------
# Mock
# ---------------------------------------------------------------------------

class MockOCRProvider(OCRProvider):
    """실제 OCR 없이 시나리오별 고정 텍스트를 반환하는 mock 구현체.

    Args:
        scenario: 반환할 시나리오 키. 기본값 'wipes'.
                  유효하지 않은 키는 DEFAULT_OCR_SCENARIO로 대체.
    """

    def __init__(self, scenario: str = DEFAULT_OCR_SCENARIO) -> None:
        self._scenario = scenario

    async def extract_text(self, image: bytes) -> str:
        return MOCK_OCR_RESULTS.get(self._scenario, MOCK_OCR_RESULTS[DEFAULT_OCR_SCENARIO])


# ---------------------------------------------------------------------------
# CLOVA OCR
# ---------------------------------------------------------------------------

class ClovaOCRProvider(OCRProvider):
    """Naver CLOVA OCR API 기반 텍스트 추출.

    현장 연결 절차:
        1. .env 에 CLOVA_OCR_API_KEY / CLOVA_OCR_API_URL 입력
        2. OCR_PROVIDER=clova 변경
        3. docker compose restart backend

    API 형식:
        POST {api_url}
        Header: X-OCR-SECRET: {api_key}
        Body:   JSON (version/requestId/images[base64])

    응답에서 fields[].inferText를 lineBreak 기준으로 줄바꿈 처리해 반환.
    """

    def __init__(self, api_key: str, api_url: str) -> None:
        self._api_key = api_key
        self._api_url = api_url

    async def extract_text(self, image: bytes) -> str:
        payload = {
            "version": "V2",
            "requestId": str(uuid.uuid4()),
            "timestamp": 0,
            "lang": "ko",
            "images": [
                {
                    "format": "jpg",
                    "name": "label",
                    "data": base64.b64encode(image).decode("utf-8"),
                }
            ],
        }
        headers = {
            "X-OCR-SECRET": self._api_key,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            response = await client.post(self._api_url, headers=headers, json=payload)
            response.raise_for_status()

        data = response.json()
        return self._parse_response(data)

    @staticmethod
    def _parse_response(data: dict[str, Any]) -> str:
        """CLOVA OCR 응답 JSON → 원시 텍스트.

        fields 배열을 순서대로 이어붙이고 lineBreak=True인 경우 줄바꿈 삽입.
        """
        try:
            fields = data["images"][0]["fields"]
        except (KeyError, IndexError):
            logger.warning("[ClovaOCR] 응답 파싱 실패: %s", data)
            return ""

        lines: list[str] = []
        current_line: list[str] = []

        for field in fields:
            current_line.append(field.get("inferText", ""))
            if field.get("lineBreak", False):
                lines.append(" ".join(current_line))
                current_line = []

        if current_line:
            lines.append(" ".join(current_line))

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Fallback 래퍼
# ---------------------------------------------------------------------------

class FallbackOCRProvider(OCRProvider):
    """primary OCR 실패 시 MockOCRProvider로 자동 전환하는 래퍼.

    실패 로그를 남기고 시연이 중단되지 않도록 보장.
    """

    def __init__(self, primary: OCRProvider) -> None:
        self._primary = primary
        self._fallback = MockOCRProvider()
        self._provider_name = type(primary).__name__

    async def extract_text(self, image: bytes) -> str:
        try:
            return await self._primary.extract_text(image)
        except Exception as exc:
            logger.warning(
                "[OCR FALLBACK] provider=%s error=%s: %s",
                self._provider_name,
                type(exc).__name__,
                exc,
            )
            return await self._fallback.extract_text(image)


# ---------------------------------------------------------------------------
# 팩토리
# ---------------------------------------------------------------------------

@lru_cache
def _build_ocr_provider(
    ocr_provider: str,
    clova_ocr_api_key: str,
    clova_ocr_api_url: str,
) -> OCRProvider:
    if ocr_provider == "clova":
        return FallbackOCRProvider(
            primary=ClovaOCRProvider(
                api_key=clova_ocr_api_key,
                api_url=clova_ocr_api_url,
            )
        )
    # mock (기본값) — fallback 불필요
    return MockOCRProvider()


def get_ocr_provider() -> OCRProvider:
    """FastAPI Depends 주입용 팩토리.

    설정 변경 시 _build_ocr_provider.cache_clear() 호출 필요.
    """
    from app.core.config import get_settings  # 순환 임포트 방지

    s = get_settings()
    return _build_ocr_provider(
        ocr_provider=s.ocr_provider,
        clova_ocr_api_key=s.clova_ocr_api_key,
        clova_ocr_api_url=s.clova_ocr_api_url,
    )
