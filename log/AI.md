# AI 개발 로그

딱콕 AI 파이프라인 개발 과정 기록.
담당: 손준혁 (AI 리드)

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
