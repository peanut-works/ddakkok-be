from abc import ABC, abstractmethod

from app.ai.ocr_mock_data import DEFAULT_OCR_SCENARIO, MOCK_OCR_RESULTS


class OCRProvider(ABC):
    """이미지에서 텍스트를 추출하는 OCR 인터페이스.

    실제 구현체: CLOVA OCR (온디바이스 ML Kit 보정 후 서버 전송)
    Mock 구현체: MockOCRProvider (시나리오별 고정 텍스트 반환)
    """

    @abstractmethod
    async def extract_text(self, image: bytes) -> str:
        """이미지 바이트를 받아 추출된 원시 텍스트를 반환한다."""


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
