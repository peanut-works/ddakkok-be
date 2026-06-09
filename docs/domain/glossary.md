# Domain Glossary

## 서비스 / 제품

**딱콕 (Ddakkok)**
영유아 보육시설 맞춤형 AI 안전 관리 서비스. 아동별 건강 데이터에 딱 맞게, 위험 성분만 콕 집어준다는 의미.

**안전 카드 (Safety Card)**
제품 분석 결과를 카드 형태로 출력한 최종 응답. 위험 성분, 판단 근거, 출처, 주의사항을 포함한다.

---

## AI 파이프라인 컴포넌트

**OCR (Optical Character Recognition)**
제품 라벨 이미지에서 텍스트를 추출하는 단계. ML Kit(온디바이스 1차) → 이미지 보정 5계층 → CLOVA OCR(서버 2차) 순으로 처리.

**NER (Named Entity Recognition) / 구조화 파싱**
OCR로 추출된 텍스트를 `{product, ingredient[], expiry, maker}` JSON으로 구조화하는 단계. GPT-4o-mini Function Calling 사용.

**Rule Checker**
제품 성분·주의사항·유통기한을 아동 프로필 및 시설 기준과 대조하여 PASS/WARN/FAIL을 판정하는 규칙 기반 엔진. LLM을 사용하지 않으므로 오탐이 없다.

**RAG (Retrieval-Augmented Generation)**
LLM 설명 생성 시 식약처 고시·화장품 안전 기준 등의 관련 문서를 pgvector에서 검색하여 컨텍스트로 제공하는 방식. LLM의 hallucination을 줄인다.

**AI Agent**
전체 검사 흐름(OCR → NER → Rule Checker → LLM)을 조율하는 오케스트레이터. FastAPI Tool Calling 기반.

---

## 판정 결과

**PASS**
제품 성분이 아동 프로필 및 시설 기준과 충돌하지 않음. 사용 가능.

**WARN**
경미한 주의가 필요한 성분 또는 조건이 있음. 교사 확인 후 사용 결정.

**FAIL**
아동의 알레르기·특이사항과 직접 충돌하거나 유통기한 초과 등 명확한 위험. 사용 보류.

---

## 도메인 데이터

**아동 프로필 (Child Profile)**
아동별 알레르기 항목, 아토피·민감 피부 여부, 특이사항을 담은 레코드.

**시설 기준 (Facility Rules)**
특정 시설에서 정한 추가 금지 성분 또는 주의 기준.

**알레르기 동의어 사전 (Allergy Synonym Dictionary)**
같은 성분이 제품마다 다르게 표기되는 문제를 보완하기 위해 자체 구축한 매핑 사전. (예: "카제인나트륨" ↔ "sodium caseinate" ↔ "우유 단백질")

---

## 외부 데이터 / API

**식약처 API**
식품의약품안전처 공공 API. 알레르기 고시, 화장품 안전 기준, 위생용품 원재료 조회에 활용.

**생활화학제품 주성분 건강유해성 데이터**
생활화학제품의 유해 가능 성분 확인 및 경고 생성에 활용하는 공공 데이터.

**유보통합 (Integrated Childcare System)**
유치원(교육부)과 어린이집(복지부) 행정 체계를 통합하는 정부 국정과제. 딱콕이 표준 안전관리 시스템으로 기여하는 정책 배경.
