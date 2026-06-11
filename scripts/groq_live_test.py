"""Groq(무료 OpenAI 호환 API) 라이브 파이프라인 테스트.

mock이 아닌 실제 LLM 호출로 NER → Rule Checker → 설명 생성 흐름을 검증한다.

    실행:  .venv\\Scripts\\python.exe scripts\\groq_live_test.py
    결과:  test_results/ 폴더에 시나리오별 JSON + _summary.json 저장

- provider는 FallbackAIProvider 래핑 없이 raw로 사용한다.
  (실패 시 mock으로 조용히 대체되면 "실제 결괏값" 검증이 안 되므로)
- 단, LabelParser/ExplanationGenerator 내부 fallback은 그대로 동작하므로
  ai.failures 로거를 후킹해 fallback 발생 여부를 결과 JSON에 기록한다.
- Rule Checker는 DB 없이 JSON 시드(07_safety_rules.json)로 동작한다.
- RAG(knowledge_loader)는 DB가 필요하므로 이 테스트에서는 생략한다.
"""

import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.ai.llm import ExplanationGenerator  # noqa: E402
from app.ai.ner import LabelParser  # noqa: E402
from app.ai.ocr_mock_data import MOCK_OCR_RESULTS  # noqa: E402
from app.ai.openai import OpenAIProvider  # noqa: E402
from app.ai.pipeline import AnalysisPipeline  # noqa: E402
from app.ai.rule_checker import ChildHealthProfile, RuleChecker  # noqa: E402
from app.core.config import get_settings  # noqa: E402

RESULTS_DIR = ROOT / "test_results"

# 시나리오 의도: wipes=FAIL(우유 알레르기), lotion=WARN(민감성 피부), sunscreen=PASS
EXPECTED = {"wipes": "FAIL", "lotion": "WARN", "sunscreen": "PASS"}

# 테스트용 아동 프로필 (시드 04_child_health_profiles.json과 동일한 구조)
CHILDREN = [
    ChildHealthProfile(child_id=1, allergies=["우유"]),
    ChildHealthProfile(child_id=2, skin_conditions=["민감성 피부"]),
    ChildHealthProfile(child_id=3),  # 특이사항 없음
]


class FallbackRecorder(logging.Handler):
    """ai.failures 로거에 찍히는 [AI FALLBACK] 메시지를 수집한다."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record.getMessage())

    def drain(self) -> list[str]:
        out, self.records = self.records, []
        return out


async def run() -> None:
    settings = get_settings()
    if not settings.groq_api_key:
        sys.exit("GROQ_API_KEY가 .env에 없습니다.")

    recorder = FallbackRecorder()
    logging.getLogger("ai.failures").addHandler(recorder)

    provider = OpenAIProvider(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        base_url=settings.groq_api_url,
        timeout=30.0,
    )

    # analyze_from_text만 사용하므로 이미지 전처리/OCR 단계는 주입하지 않는다
    pipeline = AnalysisPipeline(
        preprocessor=None,
        ocr=None,
        parser=LabelParser(provider=provider),
        checker=RuleChecker(),  # DB 없이 JSON 시드 규칙 사용
        explainer=ExplanationGenerator(provider=provider),
        knowledge_loader=None,  # RAG는 DB 필요 — 라이브 테스트에서는 생략
    )

    RESULTS_DIR.mkdir(exist_ok=True)
    summary: dict[str, object] = {
        "ran_at": datetime.now().isoformat(timespec="seconds"),
        "provider": "groq",
        "model": settings.groq_model,
        "base_url": settings.groq_api_url,
        "scenarios": {},
    }

    # 0) 연결 확인
    from app.ai.base import ChatMessage

    t0 = time.perf_counter()
    ping = await provider.chat_complete(
        [ChatMessage(role="user", content="연결 테스트입니다. '연결 성공'이라고만 답해주세요.")],
        temperature=0.0,
    )
    summary["ping"] = {"response": ping, "elapsed_sec": round(time.perf_counter() - t0, 2)}
    print(f"[ping] {ping}")

    # 1) 시나리오별 파이프라인 실행
    for scenario, ocr_text in MOCK_OCR_RESULTS.items():
        print(f"\n[{scenario}] 실행 중...")
        t0 = time.perf_counter()
        result = await pipeline.analyze_from_text(ocr_text, CHILDREN)
        elapsed = round(time.perf_counter() - t0, 2)
        fallbacks = recorder.drain()

        actual = result.safety_report.overall_status.value
        expected = EXPECTED.get(scenario, "?")
        verdict_ok = actual == expected

        record = {
            "scenario": scenario,
            "expected_status": expected,
            "actual_status": actual,
            "verdict_match": verdict_ok,
            "elapsed_sec": elapsed,
            "llm_fallbacks": fallbacks,  # 비어있어야 실제 Groq 응답
            "input_ocr_text": ocr_text,
            "ner_result": result.ner_result.model_dump(),
            "safety_report": result.safety_report.model_dump(),
            "explanation": result.explanation,
        }
        out_path = RESULTS_DIR / f"groq_{scenario}.json"
        out_path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        summary["scenarios"][scenario] = {
            "expected": expected,
            "actual": actual,
            "match": verdict_ok,
            "elapsed_sec": elapsed,
            "fallback_count": len(fallbacks),
            "result_file": out_path.name,
        }
        flag = "OK" if verdict_ok else "MISMATCH"
        print(f"[{scenario}] {expected} 예상 → {actual} ({flag}, {elapsed}s, fallback {len(fallbacks)}건)")

    (RESULTS_DIR / "groq_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n결과 저장 완료: {RESULTS_DIR}")


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(run())
