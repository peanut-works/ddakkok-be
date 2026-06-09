# Swagger Docs Sharing

BE-07 기준 API 문서 공유 방법입니다.

## 로컬 Swagger

백엔드 서버 실행 후 로컬 Swagger를 확인합니다.

```bash
docker compose up -d --build
```

```text
http://localhost:8000/docs
```

## OpenAPI YAML 생성

API 스펙이 변경될 때마다 OpenAPI YAML을 갱신합니다.

```bash
uv run python scripts/export_openapi.py
```

생성 파일:

```text
docs/openapi.yml
```

## 정적 Swagger 미리보기

생성된 `docs/openapi.yml`은 `docs/swagger/index.html`에서 읽습니다.

로컬에서 정적 Swagger를 확인하려면 아래 명령을 실행합니다.

```bash
python3 -m http.server 8080 -d docs
```

```text
http://localhost:8080/swagger/
```

## Vercel 연결

1. Vercel에 가입하거나 로그인합니다.
2. Dashboard에서 `Add New...` -> `Project`를 선택합니다.
3. Git provider로 GitHub를 연결합니다.
4. `ddakkok-be` repository를 import합니다.
5. Project Settings에서 아래처럼 설정합니다.

```text
Framework Preset: Other
Root Directory: docs
Build Command: 비워둠
Output Directory: .
Install Command: 비워둠
```

6. Deploy를 누릅니다.

배포 후 공유 URL 예시:

```text
https://<vercel-project>.vercel.app/swagger/
```

## 갱신 흐름

```text
API 코드 수정
-> uv run python scripts/export_openapi.py
-> docs/openapi.yml 변경 확인
-> commit / push
-> Vercel 자동 배포
```

정적 Swagger는 API 문서 공유용입니다. 실제 API 호출은 로컬 백엔드 또는 EC2 배포 서버에서 수행합니다.
