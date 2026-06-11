"""Kakao GMS 스펙 검증 — 현장에서 키 받자마자 실행해 gms.py TODO 4개를 판정한다.

    실행:  .venv\\Scripts\\python.exe scripts\\gms_live_test.py
    사전:  .env에 GMS_API_KEY / GMS_API_URL / GMS_MODEL 입력

검증 항목 (app/ai/gms.py의 TODO와 1:1 대응):
    1. 인증 헤더      — Authorization: Bearer가 통하는가 (401/403이면 헤더 이름 교체 필요)
    2. 엔드포인트 경로 — {GMS_API_URL}/chat/completions가 맞는가 (404면 경로 교체 필요)
    3. 응답 필드 경로  — choices[0].message.content 구조인가 (다르면 파싱 수정 필요)
    4. function calling — tools 파라미터를 지원하는가
       ※ 미지원이면 NER이 조용히 mock(물티슈 데이터)으로 폴백되어 모든 제품이
         우유 알레르기 FAIL로 판정되는 시연 사고로 이어진다. 반드시 확인할 것.

모두 통과하면 Groq 테스트와 동일한 3개 시나리오 파이프라인을 돌려
test_results/gms_*.json에 실제 결괏값을 저장한다.

GMS가 OpenAI 호환으로 확인되면: factory.py의 gms 분기를
OpenAIProvider(base_url=GMS_API_URL) 재사용으로 바꾸는 것이 더 안전하다
(Groq에서 chat + function calling까지 검증된 경로).
"""

import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402

from app.ai.base import ChatMessage  # noqa: E402
from app.ai.gms import GMSProvider  # noqa: E402
from app.ai.llm import ExplanationGenerator  # noqa: E402
from app.ai.ner import _EXTRACT_TOOL, LabelParser  # noqa: E402
from app.ai.ocr_mock_data import MOCK_OCR_RESULTS  # noqa: E402
from app.ai.pipeline import AnalysisPipeline  # noqa: E402
from app.ai.rule_checker import ChildHealthProfile, RuleChecker  # noqa: E402
from app.core.config import get_settings  # noqa: E402

RESULTS_DIR = ROOT / "test_results"
EXPECTED = {"wipes": "FAIL", "lotion": "WARN", "sunscreen": "PASS"}
CHILDREN = [
    ChildHealthProfile(child_id=1, allergies=["우유"]),
    ChildHealthProfile(child_id=2, skin_conditions=["민감성 피부"]),
    ChildHealthProfile(child_id=3),
]

PING = [
    ChatMessage(role="user", content="연결 테스트입니다. '연결 성공'이라고만 답해주세요."),
]


async def check_1_2_3_chat(provider: GMSProvider, settings) -> bool:  # noqa: ANN001
    """TODO 1(인증)·2(경로)·3(응답 필드)을 chat_complete 한 번으로 판정."""
    print("\n[검증 1~3] chat completions (인증 헤더 / 경로 / 응답 필드)")
    try:
        answer = await provider.chat_complete(PING, temperature=0.0)
        print(f"  OK — 응답: {answer[:80]}")
        print("  → 인증 Bearer / /chat/completions 경로 / choices[].message.content 모두 유효")
        return True
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        body = e.response.text[:300]
        if code in (401, 403):
            print(f"  실패 — HTTP {code}: 인증 헤더 문제일 가능성. gms.py _build_headers 수정 필요")
        elif code == 404:
            print(f"  실패 — HTTP 404: 경로 문제. gms.py _CHAT_PATH 수정 필요")
        else:
            print(f"  실패 — HTTP {code}")
        print(f"  응답 본문: {body}")
    except KeyError as e:
        print(f"  실패 — 응답 JSON에 {e} 필드 없음. gms.py 응답 파싱 경로 수정 필요")
    except Exception as e:
        print(f"  실패 — {type(e).__name__}: {e}")
    return False


async def check_4_function_call(provider: GMSProvider) -> bool:
    """TODO 4: function calling 지원 여부 — 실제 NER tool 스키마로 호출."""
    print("\n[검증 4] function calling (NER이 사용하는 tools 파라미터)")
    messages = [
        ChatMessage(role="system", content="라벨에서 제품 정보를 추출해 함수를 호출하세요."),
        ChatMessage(role="user", content="징크 선크림 SPF50+ 전성분: 정제수, 징크옥사이드, 판테놀"),
    ]
    try:
        raw = await provider.function_call(
            messages=messages,
            tools=_EXTRACT_TOOL,
            tool_choice={"type": "function", "function": {"name": "extract_product_info"}},
        )
        product = raw.get("product", "")
        if "선크림" in product or raw.get("ingredient"):
            print(f"  OK — 추출 결과: {raw}")
            return True
        print(f"  불확실 — 호출은 성공했으나 추출 결과가 비어있음: {raw}")
        return False
    except Exception as e:
        print(f"  실패 — {type(e).__name__}: {e}")
        print(
            "  ⚠ function calling 미지원이면 NER이 조용히 mock(물티슈)으로 폴백되어\n"
            "    모든 제품이 우유 알레르기 FAIL로 나오는 시연 사고가 난다.\n"
            "    → gms.py function_call()을 JSON 출력 프롬프트 방식으로 교체할 것\n"
            "      (docs/hackathon-setup.md 'GMS가 function calling을 지원하지 않는 경우' 참고)"
        )
    return False


async def run_scenarios(provider: GMSProvider, settings) -> None:  # noqa: ANN001
    """검증 통과 시 Groq 테스트와 동일한 3개 시나리오 실행 + 결과 저장."""
    print("\n[파이프라인] 3개 시나리오 실행")
    pipeline = AnalysisPipeline(
        preprocessor=None,
        ocr=None,
        parser=LabelParser(provider=provider),
        checker=RuleChecker(),
        explainer=ExplanationGenerator(provider=provider),
        knowledge_loader=None,
    )
    RESULTS_DIR.mkdir(exist_ok=True)
    summary: dict[str, object] = {
        "ran_at": datetime.now().isoformat(timespec="seconds"),
        "provider": "gms",
        "model": settings.gms_model,
        "api_url": settings.gms_api_url,
        "scenarios": {},
    }
    for scenario, ocr_text in MOCK_OCR_RESULTS.items():
        t0 = time.perf_counter()
        result = await pipeline.analyze_from_text(ocr_text, CHILDREN)
        elapsed = round(time.perf_counter() - t0, 2)
        actual = result.safety_report.overall_status.value
        expected = EXPECTED[scenario]
        flag = "OK" if actual == expected else "MISMATCH"
        print(f"  [{scenario}] {expected} 예상 → {actual} ({flag}, {elapsed}s)")

        record = {
            "scenario": scenario,
            "expected_status": expected,
            "actual_status": actual,
            "elapsed_sec": elapsed,
            "ner_result": result.ner_result.model_dump(),
            "safety_report": result.safety_report.model_dump(),
            "explanation": result.explanation,
        }
        (RESULTS_DIR / f"gms_{scenario}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        summary["scenarios"][scenario] = {"expected": expected, "actual": actual, "elapsed_sec": elapsed}

    (RESULTS_DIR / "gms_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n결과 저장 완료: {RESULTS_DIR}\\gms_*.json")


async def main() -> None:
    settings = get_settings()
    if not (settings.gms_api_key and settings.gms_api_url and settings.gms_model):
        sys.exit(".env에 GMS_API_KEY / GMS_API_URL / GMS_MODEL을 먼저 입력하세요.")

    print(f"GMS 스펙 검증 시작 — url={settings.gms_api_url} model={settings.gms_model}")
    provider = GMSProvider(
        api_key=settings.gms_api_key,
        api_url=settings.gms_api_url,
        model=settings.gms_model,
    )

    chat_ok = await check_1_2_3_chat(provider, settings)
    fc_ok = await check_4_function_call(provider) if chat_ok else False

    print("\n" + "=" * 50)
    print(f"  chat (TODO 1~3): {'통과' if chat_ok else '실패 — gms.py 수정 필요'}")
    print(f"  function calling (TODO 4): {'통과' if fc_ok else '실패 — JSON 프롬프트 대체 필요'}")
    print("=" * 50)

    if chat_ok and fc_ok:
        print("\nGMS는 OpenAI 호환으로 확인됨 — factory의 gms 분기를")
        print("OpenAIProvider(base_url=GMS_API_URL) 재사용으로 바꾸는 것도 고려 (검증된 경로).")
        await run_scenarios(provider, settings)


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
