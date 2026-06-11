"""LLM 설명 생성 — Rule Checker 결과를 교사용 설명 텍스트로 변환.

파이프라인 위치: Rule Checker(PASS/WARN/FAIL/EXPIRED/UNKNOWN) → [ExplanationGenerator] → 교사용 설명

설계 원칙:
- LLM은 위험 여부를 새로 판단하지 않는다. 판정은 Rule Checker가 완료한 것.
- matched_rules에 있는 내용만 근거로 사용한다.
- 의료적 진단 표현을 사용하지 않는다. ("알레르기 반응이 생긴다" X)
- 보호자/관리자 확인 권고 문구를 판정별로 포함한다.
- 생성 실패 시 예외 없이 RuleChecker 입력값 기반 짧은 fallback 반환.
"""

import logging
from typing import Literal

from pydantic import BaseModel

from app.ai.base import AIProvider, ChatMessage

logger = logging.getLogger(__name__)
_file_logger = logging.getLogger("ai.failures")

# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
당신은 어린이집·유치원 교사에게 제품 안전 정보를 전달하는 안내 도우미입니다.

역할:
- 제품 안전 판정은 이미 완료되었습니다. 당신의 역할은 그 결과를 교사가 이해하기 쉬운 언어로 설명하는 것입니다.
- 위험 여부를 새로 판단하거나 추가 성분 분석을 수행하지 않습니다.
- 제공된 RuleChecker 판정 결과만 쉬운 문장으로 바꿉니다.

제약:
1. matched_ingredient, matched_rule_code, reason에 있는 정보만 근거로 사용합니다.
2. RuleChecker 결과에 없는 성분, 규칙, 출처, 법령, 참고 문헌을 새로 만들지 않습니다.
3. matched_rule_code는 내부 판정 코드이므로 사용자 문장에 그대로 쓰지 않습니다.
4. "13대 알레르기", "별표", "참고 1", "참고 2", "참고 3" 같은 표현을 쓰지 않습니다.
5. 의학적 진단, 치료, 복용량, 섭취 방법 조언을 하지 않습니다.
6. 제품 유형이 명확하지 않으면 식품, 보충제, 화장품, 물티슈라고 단정하지 않습니다.
7. "필요하시면", "도와드리겠습니다" 같은 챗봇식 마무리를 쓰지 않습니다.
8. 교사용 안내 문장으로 3~5문장 이내로 작성합니다.
9. 보고서 형식, 목록, 제목 없이 일반 텍스트로 작성합니다.\
"""


def _build_system_prompt(context: list[str] | None) -> str:
    """RAG 컨텍스트가 있으면 프롬프트에 보조 정보를 추가한다."""
    if not context:
        return _SYSTEM_PROMPT
    context_section = (
        "\n\n보조 정보:"
        "\n아래 정보는 문장 이해를 돕기 위한 보조 자료입니다."
        "\n출처명, 법령명, 참고 번호를 답변에 쓰지 말고 RuleChecker 결과만 근거로 설명하세요."
    )
    for chunk in context:
        context_section += f"\n\n{chunk}"
    return _SYSTEM_PROMPT + context_section

# ── Input / Output models ─────────────────────────────────────────────────────

Verdict = Literal["PASS", "WARN", "FAIL", "EXPIRED", "UNKNOWN"]


class ExplanationInput(BaseModel):
    """설명 생성에 필요한 입력. Rule Checker가 채워서 전달한다."""

    status: Verdict
    product: str
    ingredient: list[str] = []
    matched_rules: list[str] = []
    """Rule Checker가 매칭한 규칙 설명 목록.
    예: ["카제인나트륨 — 우유 유래 성분 (아동 우유 알레르기 프로필과 충돌)"]
    PASS일 경우 빈 리스트.
    """


# ── Generator ─────────────────────────────────────────────────────────────────

_STATUS_LABEL: dict[Verdict, str] = {
    "FAIL": "❌ 사용 불가 (위험 성분 확인됨)",
    "WARN": "⚠️ 주의 필요",
    "PASS": "✅ 이상 없음",
    "EXPIRED": "⛔ 유통기한 만료",
    "UNKNOWN": "❓ 성분 확인 불가",
}


def _build_user_message(inp: ExplanationInput) -> str:
    lines = [
        f"판정 코드: {inp.status}",
        f"판정 결과: {_STATUS_LABEL[inp.status]}",
        f"제품명: {inp.product or '(알 수 없음)'}",
    ]

    if inp.ingredient:
        lines.append("성분 목록: " + ", ".join(inp.ingredient))

    if inp.matched_rules:
        lines.append("매칭된 규칙:")
        for rule in inp.matched_rules:
            lines.append(f"  - {rule}")
    else:
        lines.append("매칭된 규칙: 없음 (이상 성분 미검출)")

    lines.append(
        "\n위 정보만 바탕으로 교사에게 전달할 짧은 설명을 작성해 주세요. "
        "없는 근거를 추가하지 마세요."
    )
    return "\n".join(lines)


def _fallback_explanation(inp: ExplanationInput) -> str:
    matched_rule = inp.matched_rules[0] if inp.matched_rules else "등록된 건강 정보"
    if inp.status == "FAIL":
        return (
            "제품 성분과 등록된 건강 정보가 충돌하여 사용하지 않는 것이 좋습니다. "
            f"{matched_rule} 내용을 기준으로 위험 성분이 확인되었습니다. "
            "보호자 또는 관리자 확인 후 대체 제품 사용을 권장합니다."
        )
    if inp.status == "WARN":
        return (
            "제품 성분 중 주의가 필요한 항목이 확인되었습니다. "
            f"{matched_rule} 내용을 기준으로 주의 대상으로 분류되었습니다. "
            "사용 전 보호자 또는 관리자 확인을 권장합니다."
        )
    if inp.status == "EXPIRED":
        return (
            "유통기한이 지난 제품으로 확인되어 사용하지 않는 것이 좋습니다. "
            "관리자 확인 후 폐기 또는 대체 제품 사용을 권장합니다."
        )
    if inp.status == "UNKNOWN":
        return (
            "성분 정보를 확인할 수 없어 안전 여부를 판단하기 어렵습니다. "
            "사용 전 보호자 또는 관리자 확인이 필요합니다."
        )
    return "현재 등록된 건강 정보 기준으로 이 제품과 매칭되는 위험 성분이 없습니다."


class ExplanationGenerator:
    """Rule Checker 결과를 교사용 설명 텍스트로 변환하는 생성기.

    AIProvider를 주입받아 chat_complete를 수행한다.

    Example::

        gen = ExplanationGenerator(provider)
        text = await gen.generate(ExplanationInput(
            status="FAIL",
            product="A브랜드 물티슈",
            ingredient=["카제인나트륨"],
            matched_rules=["카제인나트륨 — 우유 유래 성분"],
        ))
    """

    def __init__(self, provider: AIProvider) -> None:
        self._provider = provider

    async def generate(
        self,
        inp: ExplanationInput,
        context: list[str] | None = None,
    ) -> str:
        """ExplanationInput을 받아 교사용 설명 문자열을 반환한다.

        Args:
            inp:     Rule Checker 결과 (status, product, ingredients, matched_rules)
            context: RAG로 검색한 관련 규정 청크 텍스트 목록. None이면 기본 프롬프트 사용.

        chat_complete 실패 시 예외 없이 RuleChecker 입력값 기반 fallback 설명 반환.
        """
        messages = [
            ChatMessage(role="system", content=_build_system_prompt(context)),
            ChatMessage(role="user", content=_build_user_message(inp)),
        ]
        try:
            return await self._provider.chat_complete(messages, temperature=0.3)
        except Exception as e:
            msg = (
                f"[AI FALLBACK] provider=ExplanationGenerator "
                f"method=generate status={inp.status} "
                f"error={type(e).__name__}: {e}"
            )
            logger.warning(msg)
            _file_logger.warning(msg)
            return _fallback_explanation(inp)
