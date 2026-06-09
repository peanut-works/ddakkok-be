"""DocTr 주름 보정 모델 래퍼 (Layer 4).

사용 전 준비:
    1. 공식 DocTr 리포에서 GeoTr.py 다운로드
         https://github.com/fh2019ustc/DocTr
       → app/services/geo_tr.py 로 저장

    2. 모델 가중치 다운로드 (GeoTr.pth)
         https://drive.google.com/file/d/1mcr7ALciuAsHCpLnrtG_eop5-EYhbCmz
       → models/doctr.pth 로 저장

    3. 의존성 설치
         uv add torch torchvision   (이미 pyproject.toml에 추가됨)

모델 파일이 없거나 로딩 실패 시 원본 이미지를 그대로 반환 (파이프라인 중단 없음).
"""

import logging
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_MODEL_PATH = Path("models/doctr.pth")
_INPUT_SIZE = 288  # DocTr GeoTr 기본 입력 해상도


class DocTrWrapper:
    """DocTr GeoTr 기반 주름 보정 래퍼.

    - 최초 호출 시 모델 로딩 (lazy init)
    - 모델 없음 / 로딩 실패 → 원본 반환
    - torch / geo_tr 임포트 실패 → 원본 반환
    """

    def __init__(self) -> None:
        self._model = None
        self._device = None
        self._tried = False

    # ------------------------------------------------------------------
    # 모델 초기화 (lazy)
    # ------------------------------------------------------------------

    def _try_load(self) -> bool:
        """모델 로딩 시도. 이미 시도했으면 캐시된 결과 반환."""
        if self._tried:
            return self._model is not None
        self._tried = True

        if not _MODEL_PATH.exists():
            logger.info(
                "[DocTr] 모델 파일 없음 (%s) — 주름 보정 비활성화\n"
                "  준비: app/services/geo_tr.py + models/doctr.pth",
                _MODEL_PATH,
            )
            return False

        try:
            import torch

            try:
                from app.services.geo_tr import GeoTr  # noqa: PLC0415
            except ImportError:
                logger.warning(
                    "[DocTr] GeoTr 임포트 실패\n"
                    "  공식 repo의 GeoTr.py를 app/services/geo_tr.py 에 배치하세요."
                )
                return False

            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            model = GeoTr(num_attn_layers=6)

            # weights_only=True: 보안상 권장이나 구형 체크포인트에서 실패 가능.
            # 실패 시 False로 재시도 (해커톤 환경에서 신뢰된 파일이므로 허용).
            try:
                state = torch.load(str(_MODEL_PATH), map_location=device, weights_only=True)
            except Exception:
                state = torch.load(str(_MODEL_PATH), map_location=device, weights_only=False)  # noqa: S614

            # 공식 체크포인트 키: model_state / state_dict / (루트 dict)
            model.load_state_dict(
                state.get("model_state", state.get("state_dict", state))
            )
            model.eval()
            model.to(device)

            self._model = model
            self._device = device
            logger.info("[DocTr] 모델 로딩 완료 (device=%s)", device)
            return True

        except Exception as exc:
            logger.warning("[DocTr] 모델 로딩 실패 — 주름 보정 비활성화: %s", exc)
            return False

    # ------------------------------------------------------------------
    # 추론
    # ------------------------------------------------------------------

    def correct(self, img: np.ndarray) -> np.ndarray:
        """DocTr 추론으로 주름 보정. 실패 시 원본 반환."""
        if not self._try_load():
            return img

        try:
            import torch

            h, w = img.shape[:2]

            # BGR(또는 그레이) → RGB 변환
            if len(img.shape) == 2:
                img_rgb = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
            else:
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            # 리사이즈 + 정규화 → tensor
            inp = (
                cv2.resize(img_rgb, (_INPUT_SIZE, _INPUT_SIZE)).astype(np.float32)
                / 255.0
            )
            tensor = (
                torch.from_numpy(inp.transpose(2, 0, 1))
                .unsqueeze(0)
                .to(self._device)
            )

            with torch.no_grad():
                output = self._model(tensor)

            # 출력: [0,1] 정규화된 재구성 이미지 (C×H×W)
            out_np = output[0].cpu().numpy().transpose(1, 2, 0)
            out_np = (out_np * 255).clip(0, 255).astype(np.uint8)
            out_np = cv2.resize(out_np, (w, h))  # 원본 해상도 복원

            # 입력이 그레이스케일이었으면 그대로 반환
            if len(img.shape) == 2:
                return cv2.cvtColor(out_np, cv2.COLOR_RGB2GRAY)
            return cv2.cvtColor(out_np, cv2.COLOR_RGB2BGR)

        except Exception as exc:
            logger.warning("[DocTr] 추론 실패 — 원본 반환: %s", exc)
            return img
