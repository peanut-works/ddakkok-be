"""pytest 공통 설정 및 테스트 전 모듈 모킹.

cv2 / numpy / torch 는 무거운 의존성으로 CI / 단위 테스트 환경에서 미설치일 수 있다.
실제 이미지 처리 로직은 app/services/image_processing.py 전용 테스트에서 커버.
파이프라인 오케스트레이션 테스트는 ImagePreprocessor 를 Mock 으로 교체하므로
실제 cv2 호출이 발생하지 않지만, 모듈 임포트 시 cv2 import 가 실행된다.
따라서 pytest 수집(collection) 전에 sys.modules 에 stub 을 삽입해 ImportError 방지.
"""

import sys
import types
from unittest.mock import MagicMock


def _make_cv2_stub() -> types.ModuleType:
    """cv2 stub 모듈 생성."""
    mod = types.ModuleType("cv2")
    # 파이프라인 테스트에서 실제로 호출되지 않지만
    # image_processing.py 가 참조하는 상수/함수 최소 정의
    for attr in (
        "IMREAD_COLOR", "THRESH_BINARY_INV", "THRESH_OTSU",
        "THRESH_BINARY", "RETR_EXTERNAL", "CHAIN_APPROX_SIMPLE",
        "INTER_CUBIC", "BORDER_REPLICATE", "INPAINT_TELEA",
        "NORM_MINMAX", "MORPH_RECT", "MORPH_CLOSE", "RANSAC",
    ):
        setattr(mod, attr, 0)
    for fn in (
        "imdecode", "imencode", "cvtColor", "threshold",
        "getRotationMatrix2D", "warpAffine", "Canny", "findContours",
        "contourArea", "arcLength", "approxPolyDP", "findHomography",
        "warpPerspective", "minAreaRect", "boundingRect",
        "getStructuringElement", "morphologyEx", "medianBlur",
        "dilate", "inpaint", "createCLAHE", "normalize",
        "DMatch", "createThinPlateSplineShapeTransformer",
        "column_stack",
    ):
        setattr(mod, fn, MagicMock(return_value=None))
    mod.COLOR_BGR2GRAY = 6  # type: ignore[attr-defined]
    return mod


def _make_numpy_stub() -> types.ModuleType:
    """numpy stub — real numpy 가 있으면 그걸 쓰고, 없으면 MagicMock."""
    try:
        import numpy as real_np
        return real_np  # type: ignore[return-value]
    except ImportError:
        mod = types.ModuleType("numpy")
        mod.ndarray = MagicMock()  # type: ignore[attr-defined]
        mod.uint8 = MagicMock()    # type: ignore[attr-defined]
        mod.float32 = MagicMock()  # type: ignore[attr-defined]
        mod.frombuffer = MagicMock()  # type: ignore[attr-defined]
        mod.array = MagicMock()    # type: ignore[attr-defined]
        mod.diff = MagicMock()     # type: ignore[attr-defined]
        mod.median = MagicMock()   # type: ignore[attr-defined]
        mod.ones = MagicMock()     # type: ignore[attr-defined]
        mod.column_stack = MagicMock()  # type: ignore[attr-defined]
        return mod


def _make_torch_stub() -> types.ModuleType:
    """torch stub — 없을 때만 삽입."""
    mod = types.ModuleType("torch")
    return mod


# pytest 수집(collection) 직전에 실행 — conftest.py 임포트 시점에 삽입
if "cv2" not in sys.modules:
    sys.modules["cv2"] = _make_cv2_stub()

if "numpy" not in sys.modules:
    sys.modules["numpy"] = _make_numpy_stub()

if "torch" not in sys.modules:
    sys.modules["torch"] = _make_torch_stub()

# _doctr 도 동일하게 stub
if "app.services._doctr" not in sys.modules:
    _doctr_stub = types.ModuleType("app.services._doctr")

    class _DocTrStub:
        def correct(self, img: object) -> object:
            return img

    _doctr_stub.DocTrWrapper = _DocTrStub  # type: ignore[attr-defined]
    sys.modules["app.services._doctr"] = _doctr_stub
