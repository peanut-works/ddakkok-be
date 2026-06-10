"""pytest 공통 설정 및 테스트 전 모듈 모킹.

루트 경로 설정:
    sys.path 에 프로젝트 루트를 추가해 `from app.xxx import ...` 임포트를 보장한다.

cv2 / numpy / torch stub:
    cv2 / numpy / torch 는 무거운 의존성으로 CI / 단위 테스트 환경에서 미설치일 수 있다.
    실제 이미지 처리 로직은 app/services/image_processing.py 전용 테스트에서 커버.
    파이프라인 오케스트레이션 테스트는 ImagePreprocessor 를 Mock 으로 교체하므로
    실제 cv2 호출이 발생하지 않지만, 모듈 임포트 시 cv2 import 가 실행된다.
    따라서 pytest 수집(collection) 전에 sys.modules 에 stub 을 삽입해 ImportError 방지.
"""

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

# ── 루트 경로 설정 ────────────────────────────────────────────────────────────

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

# ── 무거운 의존성 stub (cv2 / numpy / torch / _doctr) ─────────────────────────


def _make_cv2_stub() -> types.ModuleType:
    """cv2 stub 모듈 생성."""
    mod = types.ModuleType("cv2")
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
    """numpy stub — 설치돼 있으면 실제 numpy, 없으면 MagicMock."""
    try:
        import numpy as real_np
        return real_np  # type: ignore[return-value]
    except ImportError:
        mod = types.ModuleType("numpy")
        for attr in ("ndarray", "uint8", "float32", "frombuffer",
                     "array", "diff", "median", "ones", "column_stack"):
            setattr(mod, attr, MagicMock())  # type: ignore[attr-defined]
        return mod


def _make_torch_stub() -> types.ModuleType:
    """torch stub — 없을 때만 삽입."""
    return types.ModuleType("torch")


if "cv2" not in sys.modules:
    sys.modules["cv2"] = _make_cv2_stub()

if "numpy" not in sys.modules:
    sys.modules["numpy"] = _make_numpy_stub()

if "torch" not in sys.modules:
    sys.modules["torch"] = _make_torch_stub()

if "app.core.database" not in sys.modules:
    # database.py는 모듈 로드 시 create_engine()을 실행해 psycopg를 임포트한다.
    # 단위 테스트는 실제 DB 연결이 불필요하므로 get_db만 stub으로 제공한다.
    _db_stub = types.ModuleType("app.core.database")
    _db_stub.get_db = MagicMock()        # type: ignore[attr-defined]
    _db_stub.engine = MagicMock()        # type: ignore[attr-defined]
    _db_stub.SessionLocal = MagicMock()  # type: ignore[attr-defined]
    sys.modules["app.core.database"] = _db_stub

if "pgvector" not in sys.modules:
    import sqlalchemy.types as _sa_types

    _pgvector_stub = types.ModuleType("pgvector")
    _pgvector_sqlalchemy = types.ModuleType("pgvector.sqlalchemy")

    import sqlalchemy.sql as _sql

    class _Vector(_sa_types.UserDefinedType):  # type: ignore[misc]
        """pgvector Vector SQLAlchemy 타입 stub."""
        cache_ok = True

        class Comparator(_sa_types.UserDefinedType.Comparator):  # type: ignore[misc]
            def cosine_distance(self, other: object) -> object:
                return _sql.func.cosine_distance(self.expr, other)

            def l2_distance(self, other: object) -> object:
                return _sql.func.l2_distance(self.expr, other)

        comparator_factory = Comparator

        def __init__(self, dim: int) -> None:
            self.dim = dim

        def get_col_spec(self, **kw: object) -> str:
            return f"vector({self.dim})"

    _pgvector_sqlalchemy.Vector = _Vector  # type: ignore[attr-defined]
    sys.modules["pgvector"] = _pgvector_stub
    sys.modules["pgvector.sqlalchemy"] = _pgvector_sqlalchemy

if "app.services._doctr" not in sys.modules:
    _doctr_stub = types.ModuleType("app.services._doctr")

    class _DocTrStub:
        def correct(self, img: object) -> object:
            return img

    _doctr_stub.DocTrWrapper = _DocTrStub  # type: ignore[attr-defined]
    sys.modules["app.services._doctr"] = _doctr_stub
