# Coding Conventions

## Architecture

- 라우터는 `app/api/routes/`에 정의한다. HTTP 레이어(파라미터 파싱, 응답 직렬화)만 담당한다.
- 비즈니스 로직과 AI 서비스는 `app/services/`에 구현한다. 라우터에서 직접 DB 접근 금지.
- Pydantic 스키마는 `app/schemas/`에 정의한다. raw `dict` 반환 금지, 반드시 스키마 모델 사용.
- SQLAlchemy ORM 모델은 `app/models/`에 정의한다.
- 설정은 `app/core/config.py`의 `get_settings()`를 통해서만 접근한다. 전역 변수로 설정값을 꺼내지 않는다.
- DB 세션, 인증, 설정은 `Depends()`를 통한 의존성 주입을 사용한다. 전역 상태 금지.

## AI Pipeline

- **Rule Checker는 판정 전담**: PASS/WARN/FAIL 결정은 `app/services/rule_checker.py`의 규칙 기반 엔진이 한다.
- **LLM은 설명 생성 전용**: `app/services/llm.py`는 Rule Checker 결과를 교사용 문장으로 변환하는 역할만 한다. LLM이 직접 위험 여부를 판단하게 하지 않는다 (오탐 방지).
- AI 서비스는 `ai_provider` 설정으로 `mock` / `openai`를 전환 가능하게 구현한다. 테스트 시 mock을 사용한다.
- OCR 서비스는 `ocr_provider` 설정으로 `mock` / `clova`를 전환한다.

## Naming

- 파일명: `snake_case.py`
- 클래스: `PascalCase`
- 함수·변수: `snake_case`
- 상수: `UPPER_SNAKE_CASE`
- 라우터 파일명은 리소스명 단수형 (예: `scan.py`, `child.py`, `product.py`)

## Error Handling

- 클라이언트 오류는 `HTTPException`으로 반환한다.
- 서비스 레이어에서는 도메인 예외를 raise하고, 라우터에서 `HTTPException`으로 변환한다.
- 외부 API(OpenAI, CLOVA OCR) 호출은 타임아웃과 재시도를 명시한다.

## Testing

- `pytest` + `httpx.AsyncClient` 또는 `TestClient`로 HTTP 동작 검증.
- AI 서비스는 `ai_provider=mock`, `ocr_provider=mock`으로 단위 테스트.
- 외부 API(OpenAI, CLOVA) 호출은 테스트 게이트에 포함하지 않는다.

## Type Annotations

- 모든 함수에 리턴 타입을 명시한다 (`-> None` 포함).
- Pydantic 모델 필드는 타입 어노테이션 필수.
- `mypy --strict` 통과를 목표로 한다 (점진적으로).

## Logging

- `logging` 표준 라이브러리를 사용한다. `print()` 금지.
- AI 파이프라인 각 단계(OCR, NER, Rule Checker, LLM)에서 입출력을 DEBUG 레벨로 기록한다.

## Package Management

- 패키지 추가: `uv add <package>`
- 개발 패키지 추가: `uv add --dev <package>`
- `pip install` 직접 사용 금지. `uv.lock`이 항상 최신 상태여야 한다.
