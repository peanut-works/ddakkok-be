# AI 개발 로그

딱콕 AI 파이프라인 개발 과정 기록.
담당: 손준혁 (AI 리드)

---

## 2026-06-09 — AI-08: AI 실패 fallback 처리

### AI 호출 실패 시 시연 중단 없이 mock 응답 유지

**변경 파일**
- `app/ai/openai.py` — `timeout=15.0s` 기본값 추가
- `app/ai/gms.py` — timeout 30s → 15s (OpenAI와 통일)
- `app/ai/fallback.py` — 실패 로그를 `log/ai_failures.log`에 파일 저장 추가
- `app/api/routes/ai.py` — `/api/ai/ping` 최종 except 추가 (항상 200 반환 보장)

**실패 처리 3단 방어선**
```
1차: FallbackAIProvider — 모든 예외 잡아 mock으로 전환 (기존)
2차: log/ai_failures.log — 실패 내용 파일 기록 (AI-08 추가)
3차: api route try/except — 만일의 경우 200 + fallback 형식 반환 (AI-08 추가)
```

**ai_failures.log 기록 형식**
```
2026-06-09 07:12:45,489 WARNING [AI FALLBACK] provider=GMSProvider method=chat_complete error=ConnectError: ...
```

---

## 2026-06-09 — AI-07: GMS Client 껍데기 작성

### 현장 GMS key 수령 즉시 연결 가능한 HTTP 클라이언트 구조 구현

**변경 파일**
- `app/ai/gms.py` — `NotImplementedError` → httpx 기반 실제 HTTP 클라이언트로 교체
- `pyproject.toml` — `httpx>=0.27.0` 명시적 의존성 추가

**현장 연결 절차 (주석에도 포함)**
1. `.env`에 `GMS_API_KEY` / `GMS_API_URL` / `GMS_MODEL` 입력
2. `AI_PROVIDER=gms` 변경
3. `docker compose restart backend`
4. `GET /api/ai/ping` 으로 연결 확인

**TODO 항목 (GMS 스펙 확인 후 수정)**
- 인증 헤더 이름 (현재: `Authorization: Bearer`)
- chat completions 경로 (현재: `/chat/completions`)
- 응답 JSON 필드 경로 (현재: `choices[0].message.content`)
- function calling 지원 여부 및 응답 파싱 형식

**설계 결정**
- 스펙 미확정이므로 OpenAI 호환 형식을 기본값으로 사용
- 연결 실패 시 `FallbackAIProvider`가 mock으로 자동 전환 (기존 동작 유지)

---

## 2026-06-09 — AI-06: OpenAI 테스트 연결

### GET /api/ai/ping — AI provider 연결 테스트 엔드포인트

**변경 파일**
- `app/api/routes/ai.py` — `GET /api/ai/ping` 엔드포인트 신규
- `main.py` — ai_router 등록

**동작 방식**
| AI_PROVIDER 설정 | 동작 |
|---|---|
| `mock` | MockAIProvider 즉시 반환 (API 호출 없음) |
| `openai` | OpenAI API 최소 프롬프트 1회 호출 |
| `openai` + 잘못된 key | FallbackAIProvider → mock 자동 전환, 401 로그 출력 |

**설계 결정**
- API key는 서버 환경변수(`OPENAI_API_KEY`)에서만 읽으며 응답에 포함하지 않음
- `get_ai_provider()` Depends 주입 — provider 교체 시 엔드포인트 코드 무변경
- `temperature=0.0` — 테스트 목적이므로 결정론적 응답

---

## 2026-06-09 — AI-05: 설명 생성 프롬프트 작성

### Rule Checker 결과 → 교사용 설명 텍스트 생성

**변경 파일**
- `app/ai/llm.py` — `ExplanationInput` 모델 + `ExplanationGenerator` 클래스

**설계 결정**
- `ExplanationInput`: status(PASS/WARN/FAIL) + product + ingredient + matched_rules 입력
- `_SYSTEM_PROMPT` 제약 4가지 명시
  1. 위험 여부 재판단 금지 — 판정은 Rule Checker가 완료
  2. matched_rules 목록만 근거로 사용
  3. 의료적 진단 표현 금지 ("알레르기 반응이 생긴다" 등)
  4. 판정별 권고 문구 필수 포함 (보호자/관리자 확인 권고)
- `_build_user_message`: 판정·성분·규칙을 구조화된 텍스트로 조립해 LLM에 전달
- chat_complete 실패 시 빈 문자열 반환 (파이프라인 중단 방지)

---

## 2026-06-09 — AI-04: 라벨 파싱 프롬프트 작성

### OCR 원문 → 제품 정보 JSON 구조화 (NER)

**변경 파일**
- `app/ai/ner.py` — `NERResult` 모델 + `LabelParser` 클래스

**설계 결정**
- `LabelParser.parse(ocr_text)` → `NERResult` (product/ingredient/expiry/maker)
- `_EXTRACT_TOOL`: GPT-4o-mini Function Calling용 JSON Schema 정의
- `_SYSTEM_PROMPT`: 텍스트에 명시된 내용만 추출, 추측 금지, 실패 시 빈 값 반환 규칙 명시
- function_call 예외 시 예외 propagate 없이 빈 `NERResult()` 반환 → 파이프라인 중단 방지
- `AIProvider` 주입 방식 — Mock/OpenAI/GMS 교체 시 `LabelParser` 코드 무변경

---

## 2026-06-09 — AI-03: OCR Mock 응답 작성

### 실제 OCR 없이 제품 등록 흐름 시연용 mock 구현

**변경 파일**
- `app/ai/ocr_mock_data.py` — 시나리오별 OCR 원시 텍스트 상수 (wipes/lotion/sunscreen)
- `app/ai/ocr.py` — `OCRProvider` ABC + `MockOCRProvider` 구현

**시나리오 구성**
| 시나리오 | 제품 | 핵심 성분 | 예상 판정 |
|---|---|---|---|
| `wipes` | A브랜드 물티슈 | 카제인나트륨 (우유 유래) | FAIL |
| `lotion` | 베이비소프트 로션 | 페녹시에탄올 (영유아 주의) | WARN |
| `sunscreen` | 징크 선크림 | 문제 성분 없음 | PASS |

**설계 결정**
- `OCRProvider` ABC로 추상화 — 실제 CLOVA OCR 구현체로 교체 시 인터페이스 동일
- `MockOCRProvider`는 시나리오 키로 초기화, 잘못된 키는 `DEFAULT_OCR_SCENARIO`(wipes)로 자동 fallback
- 각 시나리오 텍스트는 실제 라벨 형식(전성분 표기, 유통기한 등) 그대로 구성 → NER 파싱 연동 가능

---

## 2026-06-09 — AI-02: Mock 설명 응답 작성

### FAIL/WARN/PASS 예시 응답 및 API 실패 fallback 구현

**변경 파일**
- `app/ai/` — AI 모듈 디렉토리 `app/services/ai/` → `app/ai/`로 이동 (import 경로 전면 수정)
- `app/ai/mock_data.py` — FAIL/WARN/PASS 판정별 교사용 설명 예시 + NER mock 결과 (신규)
- `app/ai/mock.py` — 메시지 내 키워드(FAIL/WARN/PASS) 감지 후 해당 예시 반환 (개선)
- `app/ai/fallback.py` — `FallbackAIProvider` 래퍼: primary 실패 시 mock으로 자동 전환 (신규)
- `app/ai/factory.py` — openai/gms provider를 `FallbackAIProvider`로 감싸도록 수정
- `app/ai/__init__.py` — `FallbackAIProvider` export 추가

**설계 결정**
- AI 모듈을 `app/services/ai/` 대신 `app/ai/`로 분리 — AI 파이프라인이 단순 서비스가 아닌 독립 레이어임을 구조로 표현
- `FallbackAIProvider`는 래퍼 패턴으로 구현 — primary provider 교체 없이 fallback 동작 추가 가능
- mock provider는 messages 내용 기반으로 시나리오 자동 감지 (FAIL 기본값)
- GMS key 없는 시연 환경에서도 `AI_PROVIDER=gms` 설정 그대로 유지하며 mock 응답 반환

---

## 2026-06-09 — AI-01: AI Provider 구조 설계

### AI Provider 추상화 레이어 구현

**변경 파일**
- `app/services/ai/base.py` — `AIProvider` ABC + `ChatMessage` Pydantic 모델
- `app/services/ai/mock.py` — `MockAIProvider` (고정 응답, 외부 API 없이 테스트 가능)
- `app/services/ai/openai.py` — `OpenAIProvider` (GPT-4o-mini, chat + function call)
- `app/services/ai/gms.py` — `GMSProvider` 껍데기 (`NotImplementedError`)
- `app/services/ai/factory.py` — `get_ai_provider()` 팩토리 (FastAPI `Depends` 주입용)
- `pyproject.toml` — `openai>=1.0.0` 의존성 추가

**설계 결정**
- `AIProvider`가 두 가지 메서드를 요구: `chat_complete`(설명 생성용) + `function_call`(NER 구조화 파싱용)
- `ai_provider` 설정값(`mock` / `openai` / `gms`)으로 런타임 전환 가능
- 팩토리에 `@lru_cache` 적용 — provider 인스턴스를 싱글톤으로 재사용
- LLM이 위험 판정에 관여하지 않도록 인터페이스 설계 (판정은 추후 Rule Checker 전담)

---

## 2026-06-09

### Docker 환경 — Chroma 제거, pgvector 도입

**변경 사항**
- `docker-compose.yml`: `postgres:16` → `pgvector/pgvector:pg16`
- `pyproject.toml`: `pgvector>=0.3.6` 의존성 추가

**배경**
오프라인 해커톤 환경에서 `docker compose up` 한 번으로 모든 인프라가 올라와야 함.
초기 설계에서는 RAG용 벡터 DB로 Chroma를 별도 컨테이너로 두려 했으나 아래 이유로 pgvector로 통일.

**pgvector 선택 이유**
- 컨테이너 하나 줄어들어 docker-compose 단순화
- 딱콕 RAG 지식베이스 규모(식약처 고시, 화장품 안전 기준 등 수십 건)에서 Chroma의 고성능 벡터 검색이 불필요
- 제품 저장 + 벡터 임베딩 저장을 같은 PostgreSQL 트랜잭션으로 처리 가능
- 기존 SQLAlchemy 설정 재사용 가능 (`pgvector` 라이브러리만 추가)

**트레이드오프**
Chroma 대비 ANN(Approximate Nearest Neighbor) 알고리즘 선택지가 적음.
단, 수십~수백 건 규모의 지식베이스에서는 정확 탐색(Exact Search)으로도 충분하므로 실질적 성능 차이 없음.

**다음 작업**
- pgvector extension 초기화 SQL 작성 (`CREATE EXTENSION vector`)
- SQLAlchemy 모델에 `Vector` 컬럼 타입 추가 (RAG 지식베이스 테이블)
- sentence-transformers 임베딩 서비스 구현 (`app/services/embeddings.py`)

---

## AI 파이프라인 설계 메모

### 전체 흐름
```
라벨 촬영
  → OCR (ML Kit 온디바이스 → 이미지 보정 5계층 → CLOVA OCR)
  → NER (GPT-4o-mini Function Calling → JSON)
  → Rule Checker (규칙 기반 PASS/WARN/FAIL)
  → LLM + RAG (GPT-4o-mini + pgvector 지식베이스)
  → 안전 카드 출력
```

### 핵심 설계 원칙
**위험 판정은 Rule Checker 전담, LLM은 설명 생성만.**
LLM이 직접 위험 여부를 판단하게 하면 hallucination으로 오탐 발생 가능성 있음.
Rule Checker가 PASS/WARN/FAIL을 결정하고, LLM은 그 결과를 교사가 이해하기 쉬운 문장으로 변환하는 역할만 수행.

### 구현 예정 모듈
| 파일 | 역할 | 상태 |
|------|------|------|
| `app/services/ocr.py` | OCR + 이미지 보정 | 미구현 |
| `app/services/ner.py` | GPT-4o-mini NER 파싱 | 미구현 |
| `app/services/rule_checker.py` | Rule Engine | 미구현 |
| `app/services/embeddings.py` | sentence-transformers 임베딩 | 미구현 |
| `app/services/llm.py` | RAG + LLM 설명 생성 | 미구현 |
| `app/services/agent.py` | AI Agent 조율 | 미구현 |

### RAG 지식베이스 구성 예정
- 식약처 알레르기 고시
- 화장품 안전 기준 (알레르기 유발 물질 제한)
- 생활화학제품 주성분 건강유해성 데이터
- 자체 구축 알레르기 동의어 사전
