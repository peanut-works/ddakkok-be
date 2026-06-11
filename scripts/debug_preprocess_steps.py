"""ImagePreprocessor 계층별 디버그 — 각 단계 중간 이미지를 파일로 저장.

    .venv\\Scripts\\python.exe scripts\\debug_preprocess_steps.py test_images\\test3.jpg

결과: test_results/debug_steps/<이미지명>_0_original.jpg ... _5_lighting.jpg
각 단계의 에지 밀도/대비 지표도 함께 출력한다.
"""

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from app.services.image_processing import ImagePreprocessor  # noqa: E402

OUT_DIR = ROOT / "test_results" / "debug_steps"


def load_photo_as_jpeg(path: Path) -> bytes:
    """clova_ocr_live_test.py와 동일한 로드 방식 (긴 변 2000px 축소)."""
    img = Image.open(path).convert("RGB")
    img.thumbnail((2000, 2000))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def save_jpg(path: Path, img: np.ndarray) -> None:
    """한글 경로에서도 동작하도록 imencode + Python 파일 쓰기 사용."""
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    if ok:
        path.write_bytes(buf.tobytes())


def metrics(img: np.ndarray) -> dict:
    gray = img if len(img.shape) == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    lap = cv2.Laplacian(gray, cv2.CV_64F).var()
    return {
        "edge_density": round(float(np.count_nonzero(edges)) / edges.size, 5),
        "contrast_std": round(float(gray.std()), 2),
        "laplacian_var": round(float(lap), 1),
        "shape": img.shape,
    }


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "test_images/test3.jpg")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    pre = ImagePreprocessor()
    raw = load_photo_as_jpeg(path)
    img = pre._decode(raw)

    steps = [
        ("1_deskew", pre._deskew),
        ("2_perspective", pre._perspective_restore),
        ("3_tps", pre._tps_dewarp),
        ("4_doctr", pre._doctr_unwarp),
        ("5_lighting", pre._enhance_lighting),
    ]

    stem = path.stem
    save_jpg(OUT_DIR / f"{stem}_0_original.jpg", img)
    print(f"0_original     {metrics(img)}")

    for name, fn in steps:
        before = img
        try:
            img = fn(img)
        except Exception as exc:
            print(f"{name:<14} SKIP (예외: {exc})")
            img = before
            continue
        changed = (img.shape != before.shape) or not np.array_equal(img, before)
        save_jpg(OUT_DIR / f"{stem}_{name}.jpg", img)
        print(f"{name:<14} changed={changed} {metrics(img)}")


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    main()
