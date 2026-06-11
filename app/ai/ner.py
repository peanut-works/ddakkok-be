"""NER(Named Entity Recognition) — OCR 원문을 제품 정보 JSON으로 구조화.

파이프라인 위치: OCR 원문 → [LabelParser] → NERResult → Rule Checker

설계 원칙:
- 텍스트에 명시된 내용만 추출. 추측·보완 금지.
- 추출 실패 시 예외 raise 없이 MOCK_FUNCTION_CALL_RESULT 기반 fallback NERResult 반환.
- AIProvider.function_call()을 통해 GPT-4o-mini Function Calling 사용.
  Mock 환경에서는 MockAIProvider가 MOCK_FUNCTION_CALL_RESULT를 반환.
"""

from typing import Any

from pydantic import BaseModel

from app.ai.base import AIProvider, ChatMessage

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

_EXTRACT_PRODUCT_LABEL_TOOL: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "extract_product_label",
            "description": (
                "OCR로 인식된 제품 라벨 텍스트에서 제품 등록 화면에 필요한 정보를 추출한다. "
                "텍스트에 없는 값은 null 또는 빈 배열로 반환한다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": ["string", "null"], "description": "제품명 또는 품명."},
                    "manufacturer": {
                        "type": ["string", "null"],
                        "description": "제조사, 제조업자, 책임판매업자.",
                    },
                    "expiry_date": {
                        "type": ["string", "null"],
                        "description": "YYYY-MM-DD 형식의 명확한 날짜. 별도표기는 null.",
                    },
                    "raw_ingredients_text": {
                        "type": ["string", "null"],
                        "description": "전성분 또는 성분 원문.",
                    },
                    "ingredients": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "쉼표 기준으로 분리한 성분명 목록.",
                    },
                },
                "required": [
                    "name",
                    "manufacturer",
                    "expiry_date",
                    "raw_ingredients_text",
                    "ingredients",
                ],
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

_PRODUCT_LABEL_SYSTEM_PROMPT = """\
당신은 OCR로 인식된 제품 라벨 텍스트를 제품 등록 화면용 JSON으로 구조화하는 전문가입니다.

규칙:
1. 반드시 입력 OCR text에 실제로 적힌 내용만 추출합니다.
2. 추측, 보완, 예시 데이터 사용을 금지합니다.
3. 품명 또는 제품명이 있으면 name으로 사용합니다.
4. 화장품책임판매업자, 화장품제조업자, 제조사가 있으면 manufacturer로 사용합니다.
5. 전성분 또는 성분 뒤의 원문을 raw_ingredients_text로 사용합니다.
6. ingredients는 raw_ingredients_text를 쉼표 기준으로 분리합니다.
7. 유통기한 또는 사용기한에 YYYY-MM-DD로 변환 가능한 명확한 날짜가 있을 때만 expiry_date를 채웁니다.
8. '별도표기'처럼 날짜가 명확하지 않으면 expiry_date는 null입니다.
9. 찾을 수 없는 값은 null 또는 빈 배열로 반환합니다.
10. 반드시 extract_product_label 함수를 호출합니다.\
"""


# ── Result model ──────────────────────────────────────────────────────────────

class NERResult(BaseModel):
    """NER 추출 결과. 추출 실패 시 각 필드는 빈 값."""

    product: str = ""
    ingredient: list[str] = []
    expiry: str = ""
    maker: str = ""


class ProductLabelParseResult(BaseModel):
    """제품 등록 화면용 라벨 파싱 결과."""

    name: str | None = None
    manufacturer: str | None = None
    expiry_date: str | None = None
    raw_ingredients_text: str | None = None
    ingredients: list[str] = []


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
        raw = await self._provider.function_call(
            messages=[
                ChatMessage(role="system", content=_SYSTEM_PROMPT),
                ChatMessage(role="user", content=ocr_text),
            ],
            tools=_EXTRACT_TOOL,
            tool_choice={"type": "function", "function": {"name": "extract_product_info"}},
        )
        return NERResult(
            product=raw.get("product", ""),
            ingredient=raw.get("ingredient", []),
            expiry=raw.get("expiry", ""),
            maker=raw.get("maker", ""),
        )

    async def parse_product_label(self, ocr_text: str) -> ProductLabelParseResult:
        """OCR text를 제품 등록 화면용 구조로 변환한다.

        실패 시 예외를 그대로 올려 caller가 실제 OCR text 기반 fallback을 선택하게 한다.
        mock_data.py fallback은 사용하지 않는다.
        """
        raw = await self._provider.function_call(
            messages=[
                ChatMessage(role="system", content=_PRODUCT_LABEL_SYSTEM_PROMPT),
                ChatMessage(role="user", content=ocr_text),
            ],
            tools=_EXTRACT_PRODUCT_LABEL_TOOL,
            tool_choice={"type": "function", "function": {"name": "extract_product_label"}},
        )
        ingredients = raw.get("ingredients") or []
        if not isinstance(ingredients, list):
            ingredients = []

        return ProductLabelParseResult(
            name=raw.get("name") or None,
            manufacturer=raw.get("manufacturer") or None,
            expiry_date=raw.get("expiry_date") or None,
            raw_ingredients_text=raw.get("raw_ingredients_text") or None,
            ingredients=[str(item).strip() for item in ingredients if str(item).strip()],
        )
