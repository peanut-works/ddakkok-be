# AGENTS.md

## Project Overview

- Name: ddakkok-be
- Harness profile: FastAPI
- Purpose: 영유아 보육시설 맞춤형 AI 안전 관리 서비스 백엔드. 제품 라벨 OCR → NER → Rule Checker → LLM/RAG 파이프라인을 제공하는 FastAPI 서버.
- Primary language/framework: Python 3.12 / FastAPI
- Package manager: uv (pyproject.toml + uv.lock)

## Core Rules

- 기존 아키텍처(FastAPI, uv, Docker Compose)와 디렉토리 구조를 보존한다.
- 변경은 요청된 동작에만 범위를 한정한다.
- 새로운 패키지 매니저, 프레임워크, 서비스를 추가하지 않는다. 기존 도구로 해결 가능하면 기존 것을 쓴다.
- `temp_`, `_new`, `_old`, `_backup`, `_fix` 파일을 남기지 않는다.
- `harness-starter-kit/` 클론은 읽기 전용 참조 자료다. 편집하거나 커밋하지 않는다.

## Commands

```powershell
# 린트
uv run ruff check .

# 타입 체크
uv run mypy --exclude "(harness-starter-kit|\.venv)" .

# 테스트
uv run pytest tests -v

# 전체 harness 체크 (위 세 가지 + docs drift + structure)
uv run python scripts/check_harness.py

# Docker 기반 서버 실행
make up        # 빌드 + 실행
make upd       # 백그라운드 실행
make down      # 종료
make logs      # 백엔드 로그
make shell     # 컨테이너 bash
make health    # 헬스체크 (http://localhost:8000/api/health)
```

## Project Analysis Rule

이 프로젝트를 분석·설명·온보딩할 때 아래 순서로 먼저 읽는다:

1. `README.md`
2. `AGENTS.md`
3. `docs/decisions/`
4. `docs/conventions/coding.md`
5. `docs/domain/glossary.md`
6. `docs/failures/`
7. `scripts/check_harness.py`
8. `log/AI.md` — AI 파이프라인 개발 로그

## Directory And Architecture Rules

```
ddakkok-be/
├── main.py                  # FastAPI 앱 진입점, 라우터 등록만
├── app/
│   ├── api/routes/          # 라우터 모듈 (HTTP 레이어만)
│   ├── core/config.py       # pydantic-settings, get_settings()
│   ├── models/              # SQLAlchemy ORM 모델
│   ├── schemas/             # Pydantic 요청/응답 스키마
│   └── services/            # 비즈니스 로직 + AI 서비스
├── scripts/                 # harness 체크 스크립트 (로컬 전용)
├── docs/                    # 설계 결정, 컨벤션, 도메인 용어 (로컬 전용)
├── log/AI.md                # AI 파이프라인 개발 로그
└── harness-starter-kit/     # 읽기 전용 참조 클론 (커밋 금지)
```

- **라우터**는 `app/api/routes/`에 정의한다. HTTP 레이어 외 로직은 services로 위임한다.
- **비즈니스 로직·AI 서비스**는 `app/services/`에 구현한다.
- **스키마**는 `app/schemas/`에 Pydantic 모델로 정의한다. raw dict 반환 금지.
- **설정**은 `app/core/config.py`의 `get_settings()`(lru_cache)를 통해서만 접근한다.
- **AI 판정 원칙**: Rule Checker가 PASS/WARN/FAIL 판정을 전담한다. LLM은 판정 결과를 교사용 문장으로 변환하는 역할만 한다.

## AI Pipeline Architecture

```
라벨 촬영
  → app/services/ocr.py        (ML Kit → 이미지 보정 → CLOVA OCR)
  → app/services/ner.py        (GPT-4o-mini Function Calling → JSON)
  → app/services/rule_checker.py (규칙 기반 PASS/WARN/FAIL)
  → app/services/embeddings.py   (sentence-transformers + pgvector)
  → app/services/llm.py         (RAG + GPT-4o-mini 설명 생성)
  → app/services/agent.py       (전체 흐름 조율)
```

## Knowledge Store

아키텍처·도메인·워크플로우·통합 변경 전에 먼저 읽는다:

- `docs/decisions/` — 설계 결정 기록 (ADR)
- `docs/failures/` — 장애/버그 기억
- `docs/conventions/coding.md` — 코딩 컨벤션
- `docs/domain/glossary.md` — 도메인 용어

비자명한 코드 변경 시 관련 docs를 추가하거나 갱신한다. docs를 갱신하지 않았다면 최종 보고에서 이유를 설명한다.

## Commit And PR Rules

- 브랜치명: `feature/티켓번호-작업명` (예: `feature/AI-001-ocr-service`)
- 티켓번호는 커밋 전에 사용자가 알려줌 — 번호를 받기 전에 브랜치를 생성하거나 커밋하지 않는다.
- 작업 완료 후 PR을 올린다. develop에 직접 push 금지.
- 커밋 전 `git status`와 staged diff를 확인한다.
- `harness-starter-kit/`, `.harness/`, `scripts/`, `docs/`, `AGENTS.md`는 현재 .gitignore로 커밋 제외 상태다. 팀 합의 전에는 커밋하지 않는다.

## Completion Criteria

작업 완료 전에:

- `uv run ruff check .` 통과
- `uv run pytest tests -v` 통과 (테스트가 있을 경우)
- `uv run python scripts/check_harness.py` 통과
- 임시 파일이 남아 있지 않은지 확인
- 구조적 변경이 있으면 `docs/decisions/`에 ADR 추가 또는 기존 ADR 인용
- 재현 가능한 버그 수정이면 `docs/failures/`에 기록 추가
