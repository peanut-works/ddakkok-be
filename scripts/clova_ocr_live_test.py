"""CLOVA OCR 라이브 테스트 — 라벨 이미지 → 전처리 → OCR → (Groq) NER → Rule Checker → 설명.

    합성 이미지 테스트:  .venv\\Scripts\\python.exe scripts\\clova_ocr_live_test.py
    실물 사진 테스트:    .venv\\Scripts\\python.exe scripts\\clova_ocr_live_test.py test_images\\사진.jpg
                        (여러 장 가능 — 경로를 공백으로 나열, jpg/png 지원)

    결과:  test_results/clova_<이미지명>.json

- 실물 사진은 이미지 전처리(기울기·원근·조도 보정)까지 포함한 전체 파이프라인
  (pipeline.analyze)을 탄다. DocTr 계층은 models/doctr.pth 없으면 자동 스킵.
- 합성 이미지(인자 없음)는 전처리 없이 OCR부터 실행한다.
- ClovaOCRProvider는 fallback 래퍼 없이 raw로 호출해 실제 응답을 검증한다.
"""

import asyncio
import io
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from app.ai.llm import ExplanationGenerator  # noqa: E402
from app.ai.ner import LabelParser  # noqa: E402
from app.ai.ocr import ClovaOCRProvider  # noqa: E402
from app.ai.ocr_mock_data import MOCK_OCR_RESULTS  # noqa: E402
from app.ai.openai import OpenAIProvider  # noqa: E402
from app.ai.pipeline import AnalysisPipeline  # noqa: E402
from app.ai.rule_checker import ChildHealthProfile, RuleChecker  # noqa: E402
from app.core.config import get_settings  # noqa: E402

RESULTS_DIR = ROOT / "test_results"
FONT_PATH = "C:/Windows/Fonts/malgun.ttf"
SCENARIO = "wipes"

CHILDREN = [
    ChildHealthProfile(child_id=1, allergies=["우유"]),
    ChildHealthProfile(child_id=2, skin_conditions=["민감성 피부"]),
    ChildHealthProfile(child_id=3),
]


def render_label_image(text: str) -> bytes:
    """라벨 텍스트를 흰 배경 이미지로 렌더링해 JPEG bytes로 반환한다."""
    title_font = ImageFont.truetype(FONT_PATH, 40)
    body_font = ImageFont.truetype(FONT_PATH, 28)

    lines = text.split("\n")
    img = Image.new("RGB", (900, 80 + len(lines) * 48), "white")
    draw = ImageDraw.Draw(img)

    y = 40
    for i, line in enumerate(lines):
        font = title_font if i == 0 else body_font
        draw.text((50, y), line, fill="black", font=font)
        y += 56 if i == 0 else 44

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def load_photo_as_jpeg(path: Path) -> bytes:
    """실물 사진을 JPEG bytes로 변환한다 (CLOVA 요청 format=jpg 고정이므로)."""
    img = Image.open(path).convert("RGB")
    # 너무 큰 사진은 긴 변 2000px로 축소 (CLOVA 권장 범위 + 전송량 절약)
    img.thumbnail((2000, 2000))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def _build_components(settings):  # noqa: ANN001, ANN202
    ocr = ClovaOCRProvider(
        api_key=settings.clova_ocr_api_key,
        api_url=settings.clova_ocr_api_url,
    )
    provider = OpenAIProvider(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        base_url=settings.groq_api_url,
        timeout=30.0,
    )
    return ocr, provider


def _save_record(name: str, record: dict) -> Path:
    out_path = RESULTS_DIR / f"clova_{name}.json"
    out_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


async def run_real_photos(paths: list[Path], use_preprocess: bool = True) -> None:
    """실물 사진 → 전체 파이프라인. use_preprocess=False면 원본을 바로 OCR에 보낸다."""
    settings = get_settings()
    ocr, provider = _build_components(settings)

    preprocessor = None
    if use_preprocess:
        from app.services.image_processing import get_image_preprocessor

        preprocessor = get_image_preprocessor()

    pipeline = AnalysisPipeline(
        preprocessor=preprocessor,
        ocr=ocr,  # raw — 실패 시 그대로 예외 (mock으로 가려지지 않게)
        parser=LabelParser(provider=provider),
        checker=RuleChecker(),
        explainer=ExplanationGenerator(provider=provider),
        knowledge_loader=None,
    )

    for path in paths:
        print(f"\n=== {path.name} (전처리 {'ON' if use_preprocess else 'OFF'}) ===")
        image_bytes = load_photo_as_jpeg(path)
        print(f"[1/2] 사진 로드: {len(image_bytes)} bytes (JPEG 변환·축소 후)")

        t0 = time.perf_counter()
        if use_preprocess:
            result = await pipeline.analyze(image_bytes, CHILDREN)
        else:
            ocr_text = await ocr.extract_text(image_bytes)
            result = await pipeline.analyze_from_text(ocr_text, CHILDREN)
        elapsed = round(time.perf_counter() - t0, 2)

        print(f"[2/2] OCR→NER→판정→설명 완료 ({elapsed}s) — 판정: {result.safety_report.overall_status.value}")
        print("-" * 40)
        print(result.ocr_text)
        print("-" * 40)

        record = {
            "ran_at": datetime.now().isoformat(timespec="seconds"),
            "input_image": str(path),
            "mode": "real_photo_full_pipeline" if use_preprocess else "real_photo_no_preprocess",
            "ocr_provider": "clova",
            "llm_model": settings.groq_model,
            "total_elapsed_sec": elapsed,
            "clova_ocr_text": result.ocr_text,
            "ner_result": result.ner_result.model_dump(),
            "safety_report": result.safety_report.model_dump(),
            "explanation": result.explanation,
        }
        suffix = path.stem if use_preprocess else f"{path.stem}_raw"
        out_path = _save_record(suffix, record)
        print(f"결과 저장: {out_path}")


async def run_synthetic() -> None:
    """합성 라벨 이미지 → OCR → NER → 판정 → 설명 (전처리 생략)."""
    settings = get_settings()

    label_text = MOCK_OCR_RESULTS[SCENARIO]
    image_bytes = render_label_image(label_text)
    image_path = RESULTS_DIR / f"label_{SCENARIO}.png"
    Image.open(io.BytesIO(image_bytes)).save(image_path, format="PNG")
    print(f"[1/3] 라벨 이미지 생성: {image_path} ({len(image_bytes)} bytes)")

    ocr, provider = _build_components(settings)

    t0 = time.perf_counter()
    ocr_text = await ocr.extract_text(image_bytes)
    ocr_elapsed = round(time.perf_counter() - t0, 2)
    print(f"[2/3] CLOVA OCR 완료 ({ocr_elapsed}s, {len(ocr_text)}자)")
    print("-" * 40)
    print(ocr_text)
    print("-" * 40)

    pipeline = AnalysisPipeline(
        preprocessor=None,
        ocr=None,
        parser=LabelParser(provider=provider),
        checker=RuleChecker(),
        explainer=ExplanationGenerator(provider=provider),
        knowledge_loader=None,
    )
    t0 = time.perf_counter()
    result = await pipeline.analyze_from_text(ocr_text, CHILDREN)
    rest_elapsed = round(time.perf_counter() - t0, 2)
    print(f"[3/3] NER→판정→설명 완료 ({rest_elapsed}s) — 판정: {result.safety_report.overall_status.value}")

    record = {
        "ran_at": datetime.now().isoformat(timespec="seconds"),
        "scenario": SCENARIO,
        "input_image": image_path.name,
        "mode": "synthetic_label",
        "ocr_provider": "clova",
        "ocr_elapsed_sec": ocr_elapsed,
        "original_label_text": label_text,
        "clova_ocr_text": ocr_text,
        "ner_result": result.ner_result.model_dump(),
        "safety_report": result.safety_report.model_dump(),
        "explanation": result.explanation,
        "llm_model": settings.groq_model,
        "llm_elapsed_sec": rest_elapsed,
    }
    out_path = _save_record(SCENARIO, record)
    print(f"\n결과 저장 완료: {out_path}")


async def main() -> None:
    settings = get_settings()
    RESULTS_DIR.mkdir(exist_ok=True)

    if not settings.clova_ocr_api_key or not settings.clova_ocr_api_url:
        sys.exit(
            "CLOVA_OCR_API_KEY / CLOVA_OCR_API_URL 둘 다 .env에 필요합니다.\n"
            "Invoke URL은 NCP 콘솔 > CLOVA OCR > 도메인 > APIGW 연동에서 확인하세요."
        )

    args = sys.argv[1:]
    use_preprocess = "--raw" not in args
    args = [a for a in args if a != "--raw"]
    if args:
        paths = [Path(a) for a in args]
        missing = [p for p in paths if not p.exists()]
        if missing:
            sys.exit("파일을 찾을 수 없습니다: " + ", ".join(str(p) for p in missing))
        await run_real_photos(paths, use_preprocess=use_preprocess)
    else:
        await run_synthetic()


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
