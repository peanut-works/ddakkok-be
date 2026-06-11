# 0001. TPS 곡면 복원 계층이 이미지를 파괴해 CLOVA OCR NO_TEXT 발생

## Summary

`ImagePreprocessor._tps_dewarp`(Layer 3, 곡면 복원)가 특정 실물 사진(구겨진 포장)에서
출력 이미지를 통째로 단색으로 만들어, CLOVA OCR이 NO_TEXT(ENGN-001)를 반환하고
판정이 UNKNOWN으로 떨어졌다.

- 재현 입력: `test_images/test3.jpg` (구겨진 물티슈 포장, 비스듬한 각도, 텍스트는 육안 선명)
- 전처리 ON → NO_TEXT / 전처리 OFF(`--raw`) → OCR 정상. 동일 전처리에서
  `test1.jpg`, `test2.jpg`는 정상이라 TPS 발동 조건(수평 텍스트 밴드 2개 이상)을
  충족한 사진에서만 터지는 잠복 버그였다.

## Root Cause

`cv2.createThinPlateSplineShapeTransformer` 사용법 오류 2건이 겹쳐 있었다.

1. **점 배열 형태 (치명적, 직접 원인)** — OpenCV shape 모듈의
   `estimateTransformation`은 점 집합을 `(1, N, 2)` 형태로 요구한다.
   기존 코드는 `reshape(-1, 1, 2)` 즉 `(N, 1, 2)`로 전달했고, 이 경우 변환 추정
   자체가 깨져 `warpImage` 출력의 모든 픽셀이 원본 범위 밖을 샘플링한다
   → 균일한 단색 이미지 (에지 밀도 0.034→0.000, 대비 77.7→0.0).

2. **인자 순서 (방향 반전)** — `warpImage`는 backward warping(출력 픽셀 → 입력
   픽셀 방향 매핑)을 수행하므로, 곡선을 직선으로 펴려면
   `estimateTransformation(직선 목표점, 곡선 위치점, matches)` 순서여야 한다.
   기존 코드는 `(곡선, 직선)` 순서라, 형태 버그를 고쳐도 텍스트를 펴는 게 아니라
   곡선을 오히려 증폭시킨다.

## Impact

- TPS 발동 조건을 충족하는 실물 라벨 사진(주름·곡면 포장 등 — 본래 이 계층이
  도와줘야 할 바로 그 대상)에서 OCR이 전면 실패, 분석 결과 UNKNOWN.
- 발동 조건 미충족 사진은 영향 없음 (test1/test2가 무사했던 이유).
- 두 버그가 겹쳐 있어 "TPS가 돌면 항상 파괴"였고, 형태만 고쳤다면
  "조용히 더 구부리는" 더 찾기 어려운 버그로 바뀌었을 것이다.

## Fix

`app/services/image_processing.py` `_tps_dewarp`:

- 점 배열을 `reshape(1, -1, 2)`로 변경.
- `tps.estimateTransformation(dst, src, matches)`로 순서 교정 (dst=직선 목표,
  src=곡선 위치). 각각 이유를 코드 주석으로 명시.

연구·검증 과정 (재사용 가능한 진단 도구로 저장소에 유지):

1. **계층별 분리 진단** — `scripts/debug_preprocess_steps.py`: 5계층을 단계별로
   적용하며 중간 이미지와 가독성 지표(Canny 에지 밀도, 명암 표준편차, Laplacian
   분산)를 저장. test3에서 Layer 3 직후 모든 지표가 0으로 추락하는 것을 확인해
   원인 계층을 특정했다.
2. **방향·형태 조합 실험** — `scripts/tps_direction_test.py`: 수평 텍스트 5줄을
   sin 곡선(진폭 18px)으로 휜 합성 이미지를 만들고, 점 배열 형태 × 인자 순서
   4조합을 적용해 텍스트 밴드 휘어짐(밴드 내 y중앙값 표준편차 평균)을 측정:

   | 조합 | 휘어짐 (입력 15.1px) | 결과 |
   |---|---|---|
   | `(N,1,2)` + `(src,dst)` ← 기존 | 측정 불가 | 백지 (파괴) |
   | `(N,1,2)` + `(dst,src)` | 측정 불가 | 백지 (파괴) |
   | `(1,N,2)` + `(src,dst)` | 24.5px | 곡선 증폭 |
   | `(1,N,2)` + `(dst,src)` ← 수정 | **12.0px** | 직선화 (유일한 정상) |

3. **회귀 검증** — `scripts/clova_ocr_live_test.py`로 test1~3 전처리 ON 실행:
   test3는 TPS가 실제 보정을 수행한 뒤 OCR 정상(판정 PASS, 전성분·제조업자 추출),
   test1/test2는 기존과 동일(WARN).

## Regression Check

- **품질 가드** (`_safe_apply`, [decisions/0001](../decisions/0001-preprocess-quality-guard.md)):
  보정 결과의 에지 밀도·대비가 입력 대비 절반 미만이면 해당 계층 결과를 폐기.
  동일 유형의 "보정이 이미지를 파괴" 사고가 OCR까지 전파되는 것을 런타임에 차단한다.
- **진단 스크립트 2종** (`debug_preprocess_steps.py`, `tps_direction_test.py`)을
  저장소에 유지 — 전처리 의심 사례 발생 시 계층 특정과 TPS 방향 검증을 즉시 재실행
  가능. CLOVA 라이브 테스트는 API 키·비용이 필요해 CI 게이트로는 두지 않는다.
- 주의: 이 저장소는 경로에 한글이 포함되어 `cv2.imwrite`/`cv2.imread`가 조용히
  실패한다. 진단 스크립트처럼 `cv2.imencode` + `Path.write_bytes`를 사용할 것.
