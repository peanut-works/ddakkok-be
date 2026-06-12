"""TPS estimateTransformation 인자 방향 검증.

합성 곡면 텍스트(수평 텍스트 줄을 sin 곡선으로 휨)에 대해:
    A) 현재 코드 순서:  estimateTransformation(곡선 src, 직선 dst)
    B) 뒤집은 순서:     estimateTransformation(직선 dst, 곡선 src)
를 각각 적용하고, 결과 텍스트 밴드의 '휘어짐 정도'를 수치로 비교한다.

    .venv\\Scripts\\python.exe scripts\\tps_direction_test.py

결과 이미지: test_results/tps_direction/  (한글 경로 → imencode+write_bytes로 저장)
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

OUT_DIR = ROOT / "test_results" / "tps_direction"
FONT_PATH = "C:/Windows/Fonts/malgun.ttf"


def save_jpg(path: Path, img: np.ndarray) -> None:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    if ok:
        path.write_bytes(buf.tobytes())


def make_curved_text(amplitude: float = 18.0) -> np.ndarray:
    """수평 텍스트 5줄 이미지를 만들고 sin 곡선으로 휘게 만든다."""
    font = ImageFont.truetype(FONT_PATH, 30)
    pil = Image.new("RGB", (900, 460), "white")
    draw = ImageDraw.Draw(pil)
    lines = [
        "전성분 정제수 글리세린 부틸렌글라이콜",
        "소듐벤조에이트 시트릭애씨드 폴리솔베이트",
        "라벤더추출물 로우스위트블루베리추출물",
        "사용상의 주의사항 직사광선을 피해 보관",
        "제조국 대한민국 MADE IN KOREA 150매",
    ]
    for i, line in enumerate(lines):
        draw.text((40, 40 + i * 80), line, fill="black", font=font)
    straight = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)

    h, w = straight.shape[:2]
    xs, ys = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    # 출력(x,y) ← 입력(x, y - A·sin(2πx/w)) : 텍스트가 sin 곡선을 따라 휜다
    map_y = ys - amplitude * np.sin(2 * np.pi * xs / w).astype(np.float32)
    curved = cv2.remap(
        straight, xs, map_y, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )
    return curved


def detect_bands_and_points(img: np.ndarray):
    """_tps_dewarp와 동일한 밴드 탐지 + 제어점 샘플링 로직."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    h, w = gray.shape[:2]
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(w // 10, 40), 3))
    h_morph = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, h_kernel)
    contours, _ = cv2.findContours(h_morph, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    valid = [
        c for c in contours
        if cv2.boundingRect(c)[2] > w * 0.25 and cv2.boundingRect(c)[3] < h * 0.35
    ]

    N = 8
    src_list, dst_list = [], []
    for cnt in sorted(valid, key=lambda c: cv2.boundingRect(c)[1]):
        x0, y0, bw, bh = cv2.boundingRect(cnt)
        mid_y = y0 + bh // 2
        half_step = max(bw // (N * 2), 2)
        for i in range(N + 1):
            x = x0 + i * bw // N
            near = cnt[(cnt[:, 0, 0] >= x - half_step) & (cnt[:, 0, 0] <= x + half_step)]
            y_med = int(np.median(near[:, 0, 1])) if len(near) > 0 else mid_y
            src_list.append([x, y_med])
            dst_list.append([x, mid_y])
    return valid, src_list, dst_list


def tps_warp(img: np.ndarray, flipped: bool, shape_1n2: bool) -> np.ndarray:
    """TPS 적용 — 인자 순서(flipped)와 점 배열 형태(shape_1n2) 조합 시험.

    shape_1n2=False: 현재 코드처럼 (N, 1, 2)
    shape_1n2=True:  OpenCV shape 모듈 규약대로 (1, N, 2)
    """
    _, src_list, dst_list = detect_bands_and_points(img)
    if len(src_list) < 4:
        raise RuntimeError("제어점 부족")
    shape = (1, -1, 2) if shape_1n2 else (-1, 1, 2)
    src = np.array(src_list, dtype=np.float32).reshape(shape)
    dst = np.array(dst_list, dtype=np.float32).reshape(shape)
    matches = [cv2.DMatch(i, i, 0) for i in range(len(src_list))]
    tps = cv2.createThinPlateSplineShapeTransformer()
    if flipped:
        tps.estimateTransformation(dst, src, matches)  # 직선 → 곡선 (backward)
    else:
        tps.estimateTransformation(src, dst, matches)  # 곡선 → 직선 (현재 코드)
    return tps.warpImage(img)


def waviness(img: np.ndarray) -> float:
    """텍스트 밴드의 평균 휘어짐(밴드 내 y중앙값들의 표준편차 평균). 0에 가까울수록 직선."""
    valid, src_list, _ = detect_bands_and_points(img)
    if not valid:
        return float("nan")
    devs, idx = [], 0
    N = 9  # 밴드당 제어점 수 (N=8 → 9개)
    for _ in valid:
        ys = [p[1] for p in src_list[idx: idx + N]]
        idx += N
        if ys:
            devs.append(float(np.std(ys)))
    return float(np.mean(devs))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    curved = make_curved_text()
    save_jpg(OUT_DIR / "0_curved_input.jpg", curved)
    print(f"입력(곡면)                          waviness={waviness(curved):.2f}px")

    cases = [
        ("1_n12_current", False, False, "(N,1,2) + (src,dst)  ← 현재 코드"),
        ("2_n12_flipped", True, False, "(N,1,2) + (dst,src)"),
        ("3_1n2_current", False, True, "(1,N,2) + (src,dst)"),
        ("4_1n2_flipped", True, True, "(1,N,2) + (dst,src)"),
    ]
    for name, flipped, shape_1n2, desc in cases:
        out = tps_warp(curved, flipped=flipped, shape_1n2=shape_1n2)
        save_jpg(OUT_DIR / f"{name}.jpg", out)
        print(f"{desc:<35} waviness={waviness(out):.2f}px")


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    main()
