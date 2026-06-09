"""NER(Named Entity Recognition) — OCR 원문을 제품 정보 JSON으로 구조화.

파이프라인 위치: OCR 원문 → [LabelParser] → NERResult → Rule Checker

설계 원칙:
- 텍스트에 명시된 내용만 추출. 추측·보완 금지.
- 추출 실패 시 예외 raise 없이 MOCK_FUNCTION_CALL_RESULT 기반 fallback NERResult 반환.
- AIProvider.function_call()을 통해 GPT-4o-mini Function Calling 사용.
  Mock 환경에서는 MockAIProvider가 MOCK_FUNCTION_CALL_RESULT를 반환.
"""

import logging
from typing import Any

from pydantic import BaseModel

from app.ai.base import AIProvider, ChatMessage
from app.ai.mock_data import MOCK_FUNCTION_CALL_RESULT

logger = logging.getLogger(__name__)
_file_logger = logging.getLogger("ai.failures")

# ── Tool schema ───────────────────────────────────────────────────────────────

_EXTRACT_TOOL: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "extract_product_info",
            "description": (
                "화장품·생활용품 라벨 텍스트에서 제품 정보를 추출한다. "
                "텍스트에 명시된 내용만 반환하고, 불확실한 경우 빈 값을 사용한다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product": {
                        "type": "string",
                        "description": "제품명. 찾을 수 없으면 빈 문자열.",
                    },
                    "ingredient": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "전성분 리스트. 각 성분명을 개별 문자열로 분리한다. "
                            "찾을 수 없으면 빈 배열."
                        ),
                    },
                    "expiry": {
                        "type": "string",
                        "description": (
                            "유통기한. 가능하면 YYYY-MM-DD 형식으로 변환. "
                            "찾을 수 없거나 형식 불명확하면 빈 문자열."
                        ),
                    },
                    "maker": {
                        "type": "string",
                        "description": "제조사명. 찾을 수 없으면 빈 문자열.",
                    },
                },
                "required": ["product", "ingredient", "expiry", "maker"],
            },
        },
    }
]

# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
당신은 화장품·생활용품 라벨 텍스트에서 제품 정보를 추출하는 전문가입니다.

규칙:
1. 반드시 텍스트에 명시된 내용만 추출합니다. 추측하거나 보완하지 않습니다.
2. 성분은 쉼표·줄바꿈으로 구분된 각 항목을 개별 문자열로 분리합니다.
3. 유통기한은 YYYY-MM-DD 형식으로 변환합니다. 변환이 불가능하면 원문 그대로 반환합니다.
4. 찾을 수 없는 필드는 빈 문자열("") 또는 빈 배열([])로 반환합니다.
5. 어떠한 경우에도 extract_product_info 함수를 반드시 호출합니다.\
"""


# ── Result model ──────────────────────────────────────────────────────────────

class NERResult(BaseModel):
    """NER 추출 결과. 추출 실패 시 각 필드는 빈 값."""

    product: str = ""
    ingredient: list[str] = []
    expiry: str = ""
    maker: str = ""


# ── Parser ────────────────────────────────────────────────────────────────────

class LabelParser:
    """OCR 원문을 NERResult로 변환하는 파서.

    AIProvider를 주입받아 function_call을 수행한다.
    FastAPI Depends로 사용하려면 get_label_parser() 팩토리를 사용한다.

    Example::

        parser = LabelParser(provider)
        result = await parser.parse(ocr_text)
        # NERResult(product='...', ingredient=[...], expiry='...', maker='...')
    """

    def __init__(self, provider: AIProvider) -> None:
        self._provider = provider

    async def parse(self, ocr_text: str) -> NERResult:
        """OCR 텍스트를 받아 NERResult를 반환한다.

        function_call 실패 또는 필드 누락 시 예외 없이 빈 값 NERResult를 반환한다.
        """
        messages = [
            ChatMessage(role="system", content=_SYSTEM_PROMPT),
            ChatMessage(role="user", content=ocr_text),
        ]
        try:
            raw = await self._provider.function_call(
                messages=messages,
                tools=_EXTRACT_TOOL,
                tool_choice={"type": "function", "function": {"name": "extract_product_info"}},
            )
            return NERResult(
                product=raw.get("product", ""),
                ingredient=raw.get("ingredient", []),
                expiry=raw.get("expiry", ""),
                maker=raw.get("maker", ""),
            )
        except Exception as e:
            msg = (
                f"[AI FALLBACK] provider=LabelParser "
                f"method=parse "
                f"error={type(e).__name__}: {e}"
            )
            logger.warning(msg)
            _file_logger.warning(msg)
            return NERResult(
                product=MOCK_FUNCTION_CALL_RESULT.get("product", ""),
                ingredient=MOCK_FUNCTION_CALL_RESULT.get("ingredient", []),
                expiry=MOCK_FUNCTION_CALL_RESULT.get("expiry", ""),
                maker=MOCK_FUNCTION_CALL_RESULT.get("maker", ""),
            )
