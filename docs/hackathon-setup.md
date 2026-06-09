# 해커톤 현장 세팅 가이드 (AI 파이프라인)

담당: 손준혁 (AI 리드)  
최종 업데이트: AI-10 완료 시점

---

## 체크리스트

### 현장 도착 즉시
- [ ] `.env` 파일 생성 및 API key 입력
- [ ] GMS API 스펙 받으면 `app/ai/gms.py` TODO 4개 수정
- [ ] `docker compose up -d` 실행
- [ ] `GET /api/ai/ping` 으로 AI 연결 확인

### DocTr 모델 세팅 (이미지 주름 보정)
- [ ] `GeoTr.py` → `app/services/geo_tr.py` 복사
- [ ] `GeoTr.pth` → `models/doctr.pth` 저장

### 추후 추가 예정 (AI-11 완료 후)
- [ ] CLOVA OCR API key 입력 및 `OCR_PROVIDER=clova` 변경

---

## 1. 환경변수 설정 (`.env`)

`.env.example`을 복사해 `.env` 생성 후 아래 항목 입력.

```bash
cp .env.example .env
```

### AI Provider

```env
# Kakao GMS 지급 시 → gms 로 변경. 없으면 openai 사용.
AI_PROVIDER=gms

# OpenAI 사용 시 (GMS 없을 때 fallback)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Kakao GMS 현장 지급 항목
GMS_API_KEY=...
GMS_API_URL=https://...     # 예) https://gms.kakao.com/v1
GMS_MODEL=...               # 예) gms-pro
```

### OCR (AI-11 완료 후 설정)

```env
# 현재는 mock. CLOVA 연동 완료 후 변경.
OCR_PROVIDER=clova          # mock → clova
CLOVA_OCR_API_KEY=...
CLOVA_OCR_API_URL=https://...
```

### 캐시 · 기타

```env
AI_CACHE_ENABLED=true       # 같은 요청 중복 호출 방지 (기본값 유지 권장)
AI_CACHE_MAXSIZE=256
```

---

## 2. GMS API 스펙 반영

현장에서 Kakao GMS 스펙을 받으면 `app/ai/gms.py`의 TODO 4개를 수정한다.

| 파일 위치 | TODO 내용 | 현재 가정값 |
|---|---|---|
| `_CHAT_PATH` | chat completions 엔드포인트 경로 | `/chat/completions` |
| `_build_headers()` | 인증 헤더 이름/형식 | `Authorization: Bearer` |
| `chat_complete()` 응답 파싱 | 응답 JSON 필드 경로 | `choices[0].message.content` |
| `function_call()` | function calling 지원 여부 및 응답 형식 | OpenAI 호환 가정 |

**GMS가 function calling을 지원하지 않는 경우:**  
`app/ai/gms.py` `function_call()` 안에 JSON 출력 프롬프트 방식으로 대체 구현 필요.  
(NER 파싱에 function calling 사용 중 → `app/ai/ner.py` `LabelParser` 도 영향)

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

### 시나리오 데모 테스트 (AI-15 완료 후 추가)

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

## 향후 추가 예정 세팅 항목

| AI 티켓 | 추가될 세팅 |
|---|---|
| AI-11: CLOVA OCR | `CLOVA_OCR_API_KEY`, `CLOVA_OCR_API_URL`, `OCR_PROVIDER=clova` |
| AI-16: Embeddings | pgvector extension 초기화, `python -m app.scripts.load_knowledge` 실행 |
| AI-18: 아동 프로필 연동 | 백엔드 팀 DB 모델 완성 후 Rule Checker 연동 확인 |
