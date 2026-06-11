# 딱콕 Backend

보육/영유아 교육 현장에서 제품 라벨의 성분 정보를 아동별 알러지 및 건강 프로필과 대조해 안전 사용 여부를 확인하는 FastAPI 백엔드입니다.

딱콕은 클라이언트에서 추출한 제품 라벨 OCR text를 제품 정보로 구조화하고, 저장된 제품 성분과 아동 건강 프로필을 RuleChecker로 검사한 뒤 교사용 설명과 검사 기록을 제공합니다.

## 핵심 흐름

```text
ML Kit OCR text 추출
→ OCR text 제품 정보 구조화
→ 사용자가 제품 정보 확인/수정 후 저장
→ 제품 성분과 아동 건강 프로필 RuleChecker 대조
→ 안전 검사 결과 및 교사용 설명 제공
→ 검사 기록 목록/상세 조회
```

## 기술 스택

| 구분 | 사용 기술 |
| --- | --- |
| Backend | FastAPI, Python |
| Database | PostgreSQL, pgvector 이미지 |
| ORM / Migration | SQLAlchemy, Alembic |
| Package / Run | uv |
| Container | Docker Compose |
| AI / OCR | ML Kit OCR text 입력, OpenAI/GMS/Groq provider, RuleChecker, LLM explanation |
| Test | pytest, ruff |

## 주요 기능

- mock token 기반 인증 및 API 테스트
- 제품 등록/목록/상세 조회
- `GET /api/products?barcode=...` 바코드 기반 제품 조회
- 제품 라벨 텍스트 파싱: OCR text → 제품명/성분/제조사/유통기한
- 반별 아동 목록 조회 및 건강 프로필 알러지 정보 포함
- 안전 검사 생성, 목록 조회, 상세 조회
- 저장된 안전 검사 결과 기반 교사용 설명 생성
- 홈 화면용 대시보드 요약

## 실행 방법

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec backend uv run --no-sync alembic upgrade head
docker compose exec backend uv run --no-sync python scripts/seed.py
```

서버 종료:

```bash
docker compose down
```

DB까지 초기화:

```bash
docker compose down -v
```

개발용 테스트 계정:

| 항목 | 값 |
| --- | --- |
| email | `teacher@ddakkok.com` |
| password | `ddakkok1234` |
| token | `mock-token:user:1` |

## API 문서

서버 실행 후 Swagger에서 전체 API 명세를 확인할 수 있습니다.

```text
http://localhost:8000/docs
```

## 주요 API 흐름

클라이언트 연동 기준 대표 흐름입니다.

```text
POST /api/products/parse-label-text
→ POST /api/products
→ GET /api/classrooms/{classroom_id}/children
→ POST /api/safety-checks
→ GET /api/safety-checks
→ GET /api/safety-checks/{check_id}
→ POST /api/safety-checks/{check_id}/explanations
```

### 제품 라벨 텍스트 파싱

```http
POST /api/products/parse-label-text
Authorization: Bearer mock-token:user:1
```

```json
{
  "text": "제품명: 밀크 프로틴 보습 물티슈\n제조사: 해커톤생활건강\n성분: 정제수, 글리세린, 카제인Na\n유통기한: 2027.08.31",
  "category": "WET_TISSUE"
}
```

### 안전 검사 생성

```http
POST /api/safety-checks
Authorization: Bearer mock-token:user:1
```

```json
{
  "product_id": 102,
  "classroom_id": 1,
  "child_ids": [1, 2]
}
```

검사 상세와 목록은 각각 아래 API로 조회합니다.

```text
GET /api/safety-checks
GET /api/safety-checks/{check_id}
```

## 주요 환경 변수

`.env.example` 기준 주요 변수입니다.

| 변수 | 설명 |
| --- | --- |
| `APP_ENV` | 실행 환경 |
| `APP_NAME` | 애플리케이션 이름 |
| `BACKEND_PORT` | 로컬 백엔드 포트 |
| `DATABASE_URL` | PostgreSQL 연결 URL |
| `CORS_ORIGINS` | 허용할 프론트엔드 origin 목록 |
| `AI_PROVIDER` | `mock`, `openai`, `gms`, `groq` |
| `OCR_PROVIDER` | OCR provider 설정. 기본 개발 환경은 `mock` |
| `AI_CACHE_ENABLED` | AI 캐시 사용 여부 |
| `AI_CACHE_MAXSIZE` | AI 캐시 최대 크기 |
| `OPENAI_API_KEY` | OpenAI API key |
| `OPENAI_MODEL` | OpenAI 모델명 |
| `GMS_API_KEY` | GMS API key |
| `GMS_API_URL` | GMS API URL |
| `GMS_MODEL` | GMS 모델명 |
| `GROQ_API_KEY` | Groq API key |
| `GROQ_API_URL` | Groq OpenAI 호환 API URL |
| `GROQ_MODEL` | Groq 모델명 |
| `CLOVA_OCR_API_KEY` | Clova OCR API key |
| `CLOVA_OCR_API_URL` | Clova OCR API URL |

기본 로컬 개발은 외부 AI/OCR key 없이 `AI_PROVIDER=mock`, `OCR_PROVIDER=mock`으로 실행할 수 있습니다.

## 테스트

```bash
docker compose exec backend uv run --no-sync ruff check
docker compose exec backend uv run --no-sync pytest
```

주요 API 테스트만 실행할 수도 있습니다.

```bash
docker compose exec backend uv run --no-sync pytest tests/test_products_api.py -v
docker compose exec backend uv run --no-sync pytest tests/test_safety_checks_api.py -v
docker compose exec backend uv run --no-sync pytest tests/test_children_api.py -v
```

## 향후 고도화

- 성분 출처 저장
- 내부 성분 DB 우선 조회 및 외부 성분 API fallback
- 성분 동의어 사전 확장
- 검사 결과 캐싱
- 대량 아동 검사 batch 처리
- 사용자 수정 이력 기반 AI 파싱 품질 개선
