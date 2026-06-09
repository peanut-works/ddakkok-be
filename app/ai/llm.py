"""LLM 설명 생성 — Rule Checker 결과를 교사용 설명 텍스트로 변환.

파이프라인 위치: Rule Checker(PASS/WARN/FAIL) → [ExplanationGenerator] → 교사용 설명

설계 원칙:
- LLM은 위험 여부를 새로 판단하지 않는다. 판정은 Rule Checker가 완료한 것.
- matched_rules에 있는 내용만 근거로 사용한다.
- 의료적 진단 표현을 사용하지 않는다. ("알레르기 반응이 생긴다" X)
- 보호자/관리자 확인 권고 문구를 판정별로 포함한다.
- 생성 실패 시 예외 없이 빈 문자열 반환.
"""

import logging
from typing import Literal

from pydantic import BaseModel

from app.ai.base import AIProvider, ChatMessage

logger = logging.getLogger(__name__)

# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
당신은 어린이집·유치원 교사에게 제품 안전 정보를 전달하는 안내 도우미입니다.

역할:
- 제품 안전 판정은 이미 완료되었습니다. 당신의 역할은 그 결과를 교사가 이해하기 쉬운 언어로 설명하는 것입니다.
- 위험 여부를 새로 판단하거나 추가 성분 분석을 수행하지 않습니다.
- 제공된 판정 결과와 매칭된 규칙만을 근거로 설명합니다.

제약:
1. 의료적 진단 표현 금지: "알레르기 반응이 생깁니다", "독성이 있습니다" 등 사용 금지.
   대신 "충돌 성분이 확인되었습니다", "주의가 필요한 성분이 포함되어 있습니다" 등 사용.
2. 판정별 권고 문구 필수 포함:
   - FAIL: "보호자 또는 관리자 확인 후 대체 제품 사용을 권장합니다."
   - WARN: "교사 판단 하에 사용 여부를 결정하고, 사용 후 상태를 확인해 주세요."
   - PASS: "안전하게 사용하실 수 있습니다."
3. 출처 명시: 판단 근거가 된 규칙을 간략히 인용합니다.
4. 교사가 비전문가임을 고려해 쉬운 언어를 사용합니다.\
"""

# ── Input / Output models ─────────────────────────────────────────────────────

Verdict = Literal["PASS", "WARN", "FAIL"]


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
}


def _build_user_message(inp: ExplanationInput) -> str:
    lines = [
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

    lines.append("\n위 정보를 바탕으로 교사에게 전달할 설명을 작성해 주세요.")
    return "\n".join(lines)


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

    async def generate(self, inp: ExplanationInput) -> str:
        """ExplanationInput을 받아 교사용 설명 문자열을 반환한다.

        chat_complete 실패 시 예외 없이 빈 문자열 반환.
        """
        messages = [
            ChatMessage(role="system", content=_SYSTEM_PROMPT),
            ChatMessage(role="user", content=_build_user_message(inp)),
        ]
        try:
            return await self._provider.chat_complete(messages, temperature=0.3)
        except Exception as e:
            logger.warning("ExplanationGenerator.generate 실패, 빈 문자열 반환. 원인: %s", e)
            return ""
