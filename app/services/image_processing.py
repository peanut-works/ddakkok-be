"""5계층 이미지 전처리 파이프라인.

현장 특성을 고려한 비정형 촬영 환경 대응 (슬라이드 06 기준):

    Layer 1: 기울기 정렬  — 선형 변환으로 카메라 틀어짐 수평 보정
    Layer 2: 원근 복원    — Homography 행렬로 촬영 각도 왜곡 평면화
    Layer 3: 곡면 복원    — TPS 알고리즘으로 원통형 용기 굽은 텍스트 직선화
    Layer 4: 주름 보정    — DocTr 기반 구겨진 라벨의 비선형 변형 복구
    Layer 5: 조도 개선    — CLAHE & 대비 정규화로 반사광 억제, 가독성 극대화

각 계층은 독립 실패 허용:
    한 계층에서 예외 발생 시 해당 계층만 건너뛰고 다음 계층으로 진행.
    전체 실패 시 원본 이미지 bytes를 그대로 반환.

각 계층은 품질 가드 적용:
    보정 결과의 텍스트 가독성 지표(에지 밀도, 대비)가 입력 대비 절반 이하로
    떨어지면 보정이 이미지를 파괴한 것으로 보고 해당 계층 결과를 버린다.
    (예: 주름진 포장에서 TPS 제어점이 퇴화하면 출력 전체가 단색이 되어
    OCR이 NO_TEXT를 반환하는 사례 — test_images/test3.jpg)

TPS (Layer 3) 요구 사항:
    opencv-contrib-python-headless 패키지 필요.
    (createThinPlateSplineShapeTransformer가 contrib의 shape 모듈에 포함)

DocTr (Layer 4) 요구 사항:
    app/services/geo_tr.py + models/doctr.pth 배치 필요.
    없으면 해당 계층만 스킵 (파이프라인 계속 진행).

TODO (프론트 팀 확인 후):
    ML Kit이 전송 전 어느 단계까지 전처리하는지 확인하고
    중복 계층 제거 또는 임계값 조정.
"""

import logging
from collections.abc import Callable

import cv2
import numpy as np

from app.services._doctr import DocTrWrapper

logger = logging.getLogger(__name__)

# DocTr 싱글톤 (프로세스 내 모델을 한 번만 로딩)
_doctr: DocTrWrapper | None = None


def _get_doctr() -> DocTrWrapper:
    global _doctr
    if _doctr is None:
        _doctr = DocTrWrapper()
    return _doctr


class ImagePreprocessor:
    """OCR 입력 이미지 전처리 5계층 파이프라인.

    사용 예::

        preprocessor = ImagePreprocessor()
        clean_bytes = await preprocessor.preprocess(raw_image_bytes)
    """

    async def preprocess(self, image: bytes) -> bytes:
        """원본 이미지 bytes → 전처리 완료 이미지 bytes.

        처리 중 어떤 예외가 발생해도 원본 이미지를 그대로 반환한다.
        """
        try:
            img = self._decode(image)
            if img is None:
                logger.warning("[ImagePreprocessor] 이미지 디코딩 실패 — 원본 반환")
                return image

            img = self._safe_apply(img, self._deskew, "1.기울기정렬")
            img = self._safe_apply(img, self._perspective_restore, "2.원근복원")
            img = self._safe_apply(img, self._tps_dewarp, "3.곡면복원")
            img = self._safe_apply(img, self._doctr_unwarp, "4.주름보정")
            img = self._safe_apply(img, self._enhance_lighting, "5.조도개선")

            return self._encode(img)
        except Exception as exc:
            logger.warning("[ImagePreprocessor] 전처리 실패 — 원본 반환: %s", exc)
            return image

    # ------------------------------------------------------------------
    # 내부 유틸
    # ------------------------------------------------------------------

    def _decode(self, image: bytes) -> "np.ndarray | None":
        nparr = np.frombuffer(image, np.uint8)
        return cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    def _encode(self, img: "np.ndarray") -> bytes:
        _, buffer = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
        return buffer.tobytes()

    # 품질 가드 임계 비율 — 보정 후 지표가 입력의 이 비율 미만이면 결과 폐기
    _GUARD_EDGE_RATIO = 0.5
    _GUARD_CONTRAST_RATIO = 0.5

    def _safe_apply(
        self,
        img: "np.ndarray",
        fn: "Callable[[np.ndarray], np.ndarray]",
        step_name: str,
    ) -> "np.ndarray":
        """각 계층을 예외 안전하게 실행. 실패 시 이전 단계 이미지 유지.

        실행 후 품질 가드 적용: 보정 결과의 에지 밀도/대비가 입력 대비
        절반 이하로 떨어지면 텍스트가 파괴된 것으로 판단하고 결과를 버린다.
        """
        try:
            result = fn(img)
        except Exception as exc:
            logger.warning("[ImagePreprocessor] %s 실패 — 건너뜀: %s", step_name, exc)
            return img

        if result is img:
            return img

        edge_before, contrast_before = self._readability(img)
        edge_after, contrast_after = self._readability(result)
        if (
            edge_after < edge_before * self._GUARD_EDGE_RATIO
            or contrast_after < contrast_before * self._GUARD_CONTRAST_RATIO
        ):
            logger.warning(
                "[ImagePreprocessor] %s 품질 저하 감지 — 결과 폐기 "
                "(에지밀도 %.4f→%.4f, 대비 %.1f→%.1f)",
                step_name, edge_before, edge_after, contrast_before, contrast_after,
            )
            return img
        return result

    def _readability(self, img: "np.ndarray") -> tuple[float, float]:
        """텍스트 가독성 지표: (Canny 에지 밀도, 명암 표준편차)."""
        gray = self._to_gray(img)
        edges = cv2.Canny(gray, 50, 150)
        edge_density = float(np.count_nonzero(edges)) / edges.size
        return edge_density, float(gray.std())

    def _to_gray(self, img: "np.ndarray") -> "np.ndarray":
        if len(img.shape) == 2:
            return img
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    @staticmethod
    def _sort_corners(pts: "np.ndarray") -> "np.ndarray":
        """꼭짓점 정렬: [top-left, top-right, bottom-right, bottom-left].

        합(x+y) 최소 → top-left, 최대 → bottom-right
        차(y-x) 최소 → top-right, 최대 → bottom-left
        """
        s = pts.sum(axis=1)
        d = np.diff(pts, axis=1).ravel()
        return np.array(
            [pts[s.argmin()], pts[d.argmin()], pts[s.argmax()], pts[d.argmax()]],
            dtype=np.float32,
        )

    # ------------------------------------------------------------------
    # Layer 1: 기울기 정렬 (Deskew)
    # ------------------------------------------------------------------

    def _deskew(self, img: "np.ndarray") -> "np.ndarray":
        """기울기 정렬 — 최소 외접 사각형 기반 선형 변환으로 수평 보정.

        이진화 후 텍스트 픽셀의 최소 외접 사각형 각도를 구해 보정.
        0.5° 미만은 과보정 방지를 위해 건너뜀.
        """
        gray = self._to_gray(img)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        coords = np.column_stack(np.where(binary > 0))
        if len(coords) < 10:
            return img

        angle = cv2.minAreaRect(coords)[-1]
        angle = -(90 + angle) if angle < -45 else -angle
        if abs(angle) < 0.5:
            return img

        h, w = img.shape[:2]
        M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
        return cv2.warpAffine(
            img, M, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )

    # ------------------------------------------------------------------
    # Layer 2: 원근 복원 (Homography)
    # ------------------------------------------------------------------

    def _perspective_restore(self, img: "np.ndarray") -> "np.ndarray":
        """원근 복원 — Homography + RANSAC으로 촬영 각도 왜곡 평면화.

        Canny 엣지 → 최대 윤곽 → 사각형 근사 → findHomography(RANSAC).
        이미지 면적의 15% 미만이거나 사각형을 못 찾으면 원본 유지.
        """
        gray = self._to_gray(img)
        h, w = gray.shape[:2]

        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(
            edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contours:
            return img

        largest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest) < 0.15 * h * w:
            return img

        peri = cv2.arcLength(largest, True)
        approx = cv2.approxPolyDP(largest, 0.02 * peri, True)
        if len(approx) != 4:
            return img

        src_pts = approx.reshape(4, 2).astype(np.float32)
        src_pts = self._sort_corners(src_pts)
        dst_pts = np.array(
            [[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], dtype=np.float32
        )

        H, _ = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
        if H is None:
            return img
        return cv2.warpPerspective(img, H, (w, h))

    # ------------------------------------------------------------------
    # Layer 3: 곡면 복원 (TPS)
    # ------------------------------------------------------------------

    def _tps_dewarp(self, img: "np.ndarray") -> "np.ndarray":
        """곡면 복원 — TPS(Thin Plate Spline)로 원통형 용기 굽은 텍스트 직선화.

        수평 텍스트 밴드를 탐지해 곡선 제어점 → 직선 목표점 매핑으로 TPS 보정.
        유효한 텍스트 밴드가 2개 미만이면 원본 유지.

        주의: opencv-contrib-python-headless 패키지 필요
              (createThinPlateSplineShapeTransformer가 contrib shape 모듈 소속).
        """
        gray = self._to_gray(img)
        h, w = gray.shape[:2]

        # 이진화 후 수평 방향 텍스트 밴드 강조
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        h_kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (max(w // 10, 40), 3)
        )
        h_morph = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, h_kernel)

        contours, _ = cv2.findContours(
            h_morph, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        # 너무 짧거나 높은 밴드 제외
        valid = [
            c for c in contours
            if cv2.boundingRect(c)[2] > w * 0.25
            and cv2.boundingRect(c)[3] < h * 0.35
        ]
        if len(valid) < 2:
            return img

        # 각 텍스트 밴드에서 곡선 제어점 샘플링
        N = 8  # x 방향 샘플 수
        src_list: list[list[int]] = []
        dst_list: list[list[int]] = []

        for cnt in sorted(valid, key=lambda c: cv2.boundingRect(c)[1]):
            x0, y0, bw, bh = cv2.boundingRect(cnt)
            mid_y = y0 + bh // 2
            half_step = max(bw // (N * 2), 2)

            for i in range(N + 1):
                x = x0 + i * bw // N
                # 해당 열 근방 컨투어 점의 y 중앙값 → 곡선 위치
                near = cnt[
                    (cnt[:, 0, 0] >= x - half_step) &
                    (cnt[:, 0, 0] <= x + half_step)
                ]
                y_med = int(np.median(near[:, 0, 1])) if len(near) > 0 else mid_y
                src_list.append([x, y_med])
                dst_list.append([x, mid_y])  # 직선화 목표

        if len(src_list) < 4:
            return img

        # OpenCV shape 모듈은 점 배열을 (1, N, 2) 형태로 요구한다.
        # (N, 1, 2)로 넘기면 추정이 깨져 출력 전체가 단색으로 파괴된다.
        src = np.array(src_list, dtype=np.float32).reshape(1, -1, 2)
        dst = np.array(dst_list, dtype=np.float32).reshape(1, -1, 2)
        matches = [cv2.DMatch(i, i, 0) for i in range(len(src_list))]

        tps = cv2.createThinPlateSplineShapeTransformer()
        # warpImage는 backward warping: 출력 픽셀 → 입력 픽셀 방향의 변환이
        # 필요하므로 (직선 목표 dst, 곡선 위치 src) 순서로 추정해야
        # 곡선이 직선으로 펴진다. (src, dst) 순서면 반대로 더 구부러진다.
        tps.estimateTransformation(dst, src, matches)
        result = tps.warpImage(img)
        return result if result is not None else img

    # ------------------------------------------------------------------
    # Layer 4: 주름 보정 (DocTr)
    # ------------------------------------------------------------------

    def _doctr_unwarp(self, img: "np.ndarray") -> "np.ndarray":
        """주름 보정 — DocTr 기반 구겨진 라벨의 비선형 변형 복구.

        models/doctr.pth 없으면 이 계층만 스킵 (나머지 계층 계속 진행).
        """
        return _get_doctr().correct(img)

    # ------------------------------------------------------------------
    # Layer 5: 조도 개선
    # ------------------------------------------------------------------

    def _enhance_lighting(self, img: "np.ndarray") -> "np.ndarray":
        """조도 개선 — 반사광 억제 → CLAHE → 대비 정규화.

        1. 240 이상 픽셀을 반사광으로 판단, inpaint로 주변 값 복원
        2. CLAHE (clipLimit=2.0, tileGrid=8×8) 로 국소 대비 향상
        3. 0-255 선형 정규화로 전역 대비 최대화
        """
        gray = self._to_gray(img)

        # 반사광 마스크 & 제거
        _, glare = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
        if glare.any():
            glare_dilated = cv2.dilate(glare, np.ones((5, 5), np.uint8))
            gray = cv2.inpaint(gray, glare_dilated, 3, cv2.INPAINT_TELEA)

        # CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)

        # 대비 정규화
        gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)

        return gray


def get_image_preprocessor() -> ImagePreprocessor:
    """FastAPI Depends 주입용 팩토리."""
    return ImagePreprocessor()
