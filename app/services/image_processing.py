"""이미지 전처리 서비스 — OCR 정확도 향상을 위한 5계층 보정 파이프라인.

계층 순서:
    1. 그레이스케일 변환  — 채널 단순화
    2. 노이즈 제거        — Gaussian blur (3×3)
    3. 대비 향상          — CLAHE (Contrast Limited Adaptive Histogram Equalization)
    4. 기울기 보정        — 최소 외접 사각형 회전각 기반 deskew
    5. 곡률 보정          — 최대 사각형 윤곽 기반 원근 변환 (dewarp)

각 계층은 독립 실패 허용:
    한 계층에서 예외 발생 시 해당 계층만 건너뛰고 다음 계층으로 진행.
    전체 파이프라인 실패 시 원본 이미지 bytes를 그대로 반환.

TODO (프론트 팀 확인 후):
    - ML Kit에서 어느 단계까지 전처리 후 전송하는지 확인
    - 전처리 범위 중복 제거 (예: ML Kit이 이미 그레이스케일 처리 시 1계층 스킵)
"""

import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)


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

            img = self._safe_apply(img, self._to_grayscale, "1.그레이스케일")
            img = self._safe_apply(img, self._denoise, "2.노이즈제거")
            img = self._safe_apply(img, self._enhance_contrast, "3.대비향상")
            img = self._safe_apply(img, self._deskew, "4.기울기보정")
            img = self._safe_apply(img, self._dewarp, "5.곡률보정")

            return self._encode(img)
        except Exception as exc:
            logger.warning("[ImagePreprocessor] 전처리 실패 — 원본 반환: %s", exc)
            return image

    # ------------------------------------------------------------------
    # 내부 유틸
    # ------------------------------------------------------------------

    def _decode(self, image: bytes) -> "np.ndarray | None":
        nparr = np.frombuffer(image, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img  # 디코딩 실패 시 None

    def _encode(self, img: "np.ndarray") -> bytes:
        _, buffer = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
        return buffer.tobytes()

    def _safe_apply(
        self,
        img: "np.ndarray",
        fn: "callable",
        step_name: str,
    ) -> "np.ndarray":
        """각 계층을 예외 안전하게 실행. 실패 시 이전 단계 이미지 유지."""
        try:
            return fn(img)
        except Exception as exc:
            logger.warning("[ImagePreprocessor] %s 실패 — 건너뜀: %s", step_name, exc)
            return img

    # ------------------------------------------------------------------
    # 5계층 구현
    # ------------------------------------------------------------------

    def _to_grayscale(self, img: "np.ndarray") -> "np.ndarray":
        """1계층: 그레이스케일 변환.

        BGR 3채널 → 단채널로 변환해 이후 처리 단순화.
        이미 그레이스케일이면 그대로 반환.
        """
        if len(img.shape) == 2:
            return img
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    def _denoise(self, img: "np.ndarray") -> "np.ndarray":
        """2계층: 노이즈 제거 — Gaussian blur.

        3×3 커널로 카메라 센서 노이즈와 JPEG 압축 아티팩트 제거.
        텍스트 엣지 보존을 위해 커널 크기를 최소로 유지.
        """
        return cv2.GaussianBlur(img, (3, 3), 0)

    def _enhance_contrast(self, img: "np.ndarray") -> "np.ndarray":
        """3계층: 대비 향상 — CLAHE.

        전역 히스토그램 평활화와 달리 타일 단위로 적용해
        라벨 일부가 그늘지거나 과노출되어도 전체 텍스트 가독성 유지.
        """
        gray = img if len(img.shape) == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        return clahe.apply(gray)

    def _deskew(self, img: "np.ndarray") -> "np.ndarray":
        """4계층: 기울기 보정 (deskew).

        이진화 후 어두운 픽셀의 최소 외접 사각형 회전각을 구해 보정.
        0.5° 미만 기울기는 보정하지 않는다 (과보정 방지).
        """
        gray = img if len(img.shape) == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
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

    def _dewarp(self, img: "np.ndarray") -> "np.ndarray":
        """5계층: 곡률 보정 (dewarp) — 원근 변환.

        Canny 엣지 → 최대 윤곽 → 사각형 근사 → 원근 변환 순으로 처리.

        조건을 만족하지 못하면 원본 유지:
        - 사각형 윤곽(꼭짓점 4개)을 찾지 못한 경우
        - 윤곽 면적이 이미지 면적의 20% 미만인 경우 (라벨이 화면 대부분을 차지해야 함)

        TODO: ML Kit이 전송 전 촬영 프레임을 어느 수준까지 보정하는지 확인 후
              이 계층의 임계값(20%) 조정 필요.
        """
        gray = img if len(img.shape) == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape[:2]

        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(
            edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contours:
            return img

        largest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest) < 0.20 * h * w:
            return img

        peri = cv2.arcLength(largest, True)
        approx = cv2.approxPolyDP(largest, 0.02 * peri, True)
        if len(approx) != 4:
            return img

        pts = approx.reshape(4, 2).astype(np.float32)
        pts = self._sort_corners(pts)
        dst = np.array(
            [[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]],
            dtype=np.float32,
        )
        M = cv2.getPerspectiveTransform(pts, dst)
        return cv2.warpPerspective(img, M, (w, h))

    @staticmethod
    def _sort_corners(pts: "np.ndarray") -> "np.ndarray":
        """꼭짓점 정렬: [top-left, top-right, bottom-right, bottom-left].

        합(x+y)이 최소 → top-left, 최대 → bottom-right
        차(y-x)가 최소 → top-right, 최대 → bottom-left
        """
        s = pts.sum(axis=1)
        d = np.diff(pts, axis=1).ravel()
        return np.array(
            [pts[s.argmin()], pts[d.argmin()], pts[s.argmax()], pts[d.argmax()]],
            dtype=np.float32,
        )


def get_image_preprocessor() -> ImagePreprocessor:
    """FastAPI Depends 주입용 팩토리.

    ImagePreprocessor는 상태가 없으므로 매 요청마다 새 인스턴스를 반환해도 무방하나,
    향후 설정 주입이 필요한 경우 이 팩토리에서 처리한다.
    """
    return ImagePreprocessor()
