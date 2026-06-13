# 해커톤 현장 세팅 가이드 (AI 파이프라인)

담당: 손준혁 (AI 리드)  
최종 업데이트: AI-12 완료 시점

---

## 체크리스트

### 현장 도착 즉시
- [ ] `.env` 파일 생성 및 API key 입력
- [ ] `docker compose up -d` 실행
- [ ] `GET /api/ai/ping` 으로 AI 연결 확인

### DocTr 모델 세팅 (이미지 주름 보정)
- [ ] `GeoTr.py` → `app/services/geo_tr.py` 복사
- [ ] `GeoTr.pth` → `models/doctr.pth` 저장

### CLOVA OCR 세팅
- [ ] CLOVA OCR API key / URL 입력
- [ ] `OCR_PROVIDER=clova` 변경 후 `docker compose restart backend`

---

## 1. 환경변수 설정 (`.env`)

`.env.example`을 복사해 `.env` 생성 후 아래 항목 입력.

```bash
cp .env.example .env
```

### AI Provider

GMS는 OpenAI 호환 API다. base_url만 GMS로 바꾸면 OpenAI SDK 그대로 사용된다.

```env
# SSAFY GMS 지급 시 → gms 로 변경. 없으면 openai 사용.
AI_PROVIDER=gms

# OpenAI 사용 시 (GMS 없을 때 fallback)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# SSAFY GMS 현장 지급 항목
GMS_API_KEY=...
GMS_API_URL=https://gms.ssafy.io/gmsapi/api.openai.com/v1
GMS_MODEL=gpt-4o-mini       # GMS가 지원하는 모델명
```

### OCR

```env
# 현재는 mock. CLOVA key 수령 후 변경.
OCR_PROVIDER=clova              # mock → clova
CLOVA_OCR_API_KEY=...           # Naver Cloud Console에서 발급
CLOVA_OCR_API_URL=https://...   # 예) https://ocr.apigw.ntruss.com/custom/v1/XXXXX/...
```

### 캐시 · 기타

```env
AI_CACHE_ENABLED=true       # 같은 요청 중복 호출 방지 (기본값 유지 권장)
AI_CACHE_MAXSIZE=256
```

---

## 2. GMS 연동 (코드 수정 불필요)

GMS는 OpenAI 호환 API이므로 별도 provider 구현이 필요 없다.
`app/ai/factory.py`가 `AI_PROVIDER=gms`일 때 `OpenAIProvider`에 `base_url=GMS_API_URL`만
바꿔 재사용한다. chat completions / function calling 모두 OpenAI SDK 형식 그대로 동작한다.

`.env`에 GMS 값 입력 후 `docker compose up -d backend`로 컨테이너를 재생성하면 적용된다.
(`docker compose restart`는 env를 재로드하지 않으므로 `up -d`를 사용한다.)

---

## 3. DocTr 모델 세팅 (이미지 주름 보정 Layer 4)

### 파일 배치

```bash
# 1. GeoTr 모델 코드 (공식 DocTr repo)
#    https://github.com/fh2019ustc/DocTr/blob/main/GeoTr.py
cp GeoTr.py app/services/geo_tr.py

# 2. 모델 가중치 (~200 MB)
#    Google Drive: https://drive.google.com/file/d/1mcr7ALciuAsHCpLnrtG_eop5-EYhbCmz
mv GeoTr.pth models/doctr.pth
```

### 동작 확인

서버 로그에서 확인:
```
[DocTr] 모델 로딩 완료 (device=cpu)
```

**모델 없어도 괜찮음:** Layer 4만 스킵하고 나머지 4계층(기울기·원근·곡면·조도)은 정상 동작.  
로그에 `[DocTr] 모델 파일 없음 — 주름 보정 비활성화` 출력되면 정상 스킵 중.

---

## 4. Docker 실행

```bash
# 전체 서비스 시작 (백엔드 + PostgreSQL/pgvector)
docker compose up -d

# 로그 확인
docker compose logs -f backend

# 재시작 (설정 변경 후)
docker compose restart backend
```

---

## 5. 연결 검증

### AI Provider 확인

```bash
curl http://localhost:8000/api/ai/ping
```

| 응답 | 의미 |
|---|---|
| `{"status": "ok", "provider": "gms", ...}` | GMS 정상 연결 |
| `{"status": "ok", "provider": "openai", ...}` | OpenAI 정상 연결 |
| `{"status": "fallback", ...}` | API 호출 실패 → mock 자동 전환 (시연 가능) |

### 시나리오 데모 테스트 (AI-13 완료 후 추가)

```bash
# 세 가지 시나리오로 전체 파이프라인 테스트
curl "http://localhost:8000/api/ai/analyze/demo?scenario=wipes"    # → FAIL (우유 알레르기)
curl "http://localhost:8000/api/ai/analyze/demo?scenario=lotion"   # → WARN (페녹시에탄올)
curl "http://localhost:8000/api/ai/analyze/demo?scenario=sunscreen" # → PASS
```

---

## 6. Fallback 동작 (시연 중 AI 장애 시)

어떤 상황에도 API는 200 응답을 반환하도록 설계됨:

```
GMS/OpenAI 호출 실패
  → FallbackAIProvider가 Mock 응답으로 자동 전환
  → log/ai_failures.log 에 실패 내용 기록
  → 시연 화면에는 정상 안전카드 표시
```

AI 장애 발생 시 로그 확인:
```bash
tail -f log/ai_failures.log
```

---

---

## 7. Rule Checker 데이터 파일 (BE-13 — 별도 세팅 불필요)

서버 시작 시 자동 로딩. 파일이 없으면 서버가 뜨지 않으므로 경로 확인 필수.

| 파일 | 역할 |
|---|---|
| `app/data/01_seed/07_safety_rules.json` | 위험 성분 규칙 8개 (ALLERGY/SKIN/EXPIRY/UNKNOWN) |
| `app/data/01_seed/06_ingredient_aliases.json` | 성분 별칭 정규화 사전 (카제인Na → 카제인나트륨 등) |

```bash
# 파일 존재 확인
ls app/data/01_seed/07_safety_rules.json
ls app/data/01_seed/06_ingredient_aliases.json
```

현장에서 규칙 추가 필요 시 JSON 파일 직접 수정 → 서버 재시작으로 반영.

---

## 8. 파이프라인 오케스트레이터 (AI-12 — 별도 세팅 불필요)

`AnalysisPipeline`이 아래 컴포넌트를 자동으로 연결:

```
이미지 bytes
  → ImagePreprocessor  (기울기·원근·곡면·주름·조도 보정)
  → OCRProvider        (mock 또는 CLOVA — .env 설정 따름)
  → LabelParser        (NER — mock 또는 OpenAI/GMS — .env 설정 따름)
  → RuleChecker        (JSON 규칙 파일 × 아동 프로필 대조)
  → ExplanationGenerator (교사용 설명 — mock 또는 OpenAI/GMS)
  → PipelineResult
```

각 컴포넌트는 독립 실패 허용 — 어느 단계가 실패해도 fallback으로 자동 전환되어
시연이 중단되지 않음.

---

## 향후 추가 예정 세팅 항목

| 티켓 | 추가될 세팅 |
|---|---|
| AI-13: 안전카드 API | 이미지 업로드 엔드포인트 — 별도 env 불필요 |
| AI-14: Embeddings | pgvector extension 초기화, `python -m app.scripts.load_knowledge` 실행 |
| AI-15: RAG | 지식 베이스 로딩 완료 후 확인 |
