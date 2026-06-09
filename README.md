# ddakkok-be

영유아 맞춤 제품 안전관리 서비스 **딱콕** 백엔드 레포지토리입니다.

## 기술 스택

* Python 3.11
* FastAPI
* uv
* PostgreSQL
* Docker Compose

## 실행 전 준비

Docker와 uv가 필요합니다.

Mac 기준 uv 설치:

```bash
brew install uv
```

## 환경변수 설정

`.env.example` 파일을 복사해서 `.env` 파일을 생성합니다.

```bash
cp .env.example .env
```

기본 개발 환경에서는 아래 값으로 실행합니다.

```env
APP_ENV=local
APP_NAME=ddakkok-be

DATABASE_URL=postgresql+psycopg://ddakkok:ddakkok@db:5432/ddakkok

CORS_ORIGINS=http://localhost:5173,http://localhost:3000

AI_PROVIDER=mock
OCR_PROVIDER=mock
```

실제 API key는 `.env`에만 작성하고 Git에 커밋하지 않습니다.

## Docker Compose 실행

백엔드와 PostgreSQL을 함께 실행합니다.

```bash
docker compose up --build
```

백그라운드 실행:

```bash
docker compose up -d --build
```

컨테이너 종료:

```bash
docker compose down
```

DB volume까지 삭제하고 초기화:

```bash
docker compose down -v
```

## Makefile 명령어

```bash
make up
```

백엔드와 DB를 foreground로 실행합니다.

```bash
make upd
```

백엔드와 DB를 background로 실행합니다.

```bash
make down
```

컨테이너를 종료합니다.

```bash
make reset-db
```

DB volume을 삭제하고 컨테이너를 다시 실행합니다.

```bash
make logs
```

백엔드 로그를 확인합니다.

## API 확인

서버 실행 후 아래 주소에서 확인할 수 있습니다.

```text
http://localhost:8000
```

Health check:

```text
http://localhost:8000/api/health
```

Swagger:

```text
http://localhost:8000/docs
```

## DB 마이그레이션

Docker Compose 실행 후 Alembic migration을 적용합니다.

```bash
docker compose exec backend uv run --no-sync alembic upgrade head
```

## Seed 데이터 삽입

Migration 적용 후 seed 데이터를 삽입합니다.

```bash
docker compose exec backend uv run --no-sync python scripts/seed.py
```

개발용 테스트 계정:

```text
email: teacher@ddakkok.com
password: ddakkok1234
token: mock-token:user:1 
```

로그인 API:

```text
POST /api/auth/login
POST /api/auth/demo
GET /api/auth/me
```

자세한 seed 데이터 구성과 확인 명령은 [docs/seed.md](docs/seed.md)를 참고합니다.

## 프론트엔드 연동

Vite 프론트엔드 로컬 주소는 CORS 허용 목록에 포함되어 있습니다.

```text
http://localhost:5173
```

## AI Provider 기준

기본 개발 환경에서는 mock provider를 사용합니다.

```env
AI_PROVIDER=mock
OCR_PROVIDER=mock
```

GMS 또는 OpenAI key가 없어도 기본 시연 흐름이 끊기지 않도록 mock 응답을 우선 사용합니다.

향후 필요 시 아래 값으로 전환합니다.

```env
AI_PROVIDER=openai
AI_PROVIDER=gms
```

API key는 반드시 백엔드 `.env`에서만 관리하고, 프론트엔드에 노출하지 않습니다.


## 프로젝트 구조

```text
app/
  api/
    routes/        # 기능별 API 라우터
  core/            # 환경변수, DB 연결, 공통 설정
  models/          # SQLAlchemy DB 모델
  schemas/         # Pydantic 요청/응답 스키마
  services/        # 비즈니스 로직
  ai/              # AI provider, prompt, mock 응답
  main.py          # FastAPI 앱 생성, CORS 설정, router 등록

data/
  raw/             # 공공데이터/외부 데이터 원본 정리본
  seed/            # DB seed로 삽입할 데이터
  mock/            # OCR/AI mock 응답 데이터
  demo/            # 시연용 고정 시나리오 데이터
```
