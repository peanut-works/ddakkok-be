### 1. 화장품 동의어

`https://www.data.go.kr/data/15111774/openapi.do#/`

-- 출력 예시 | 검색어: 카제인 --
```json
{
  "header": {
    "resultCode": "00",
    "resultMsg": "NORMAL SERVICE."
  },
  "body": {
    "pageNo": 1,
    "totalCount": 2,
    "numOfRows": 10,
    "items": [
      {
        "INGR_KOR_NAME": "하이드록시프로필트라이모늄하이드롤라이즈드카제인",
        "INGR_ENG_NAME": "Hydroxypropyltrimonium Hydrolyzed Casein",
        "CAS_NO": null,
        "ORIGIN_MAJOR_KOR_NAME": "이 원료는 주로 하이드록시프로필트라이메틸아민과 가수분해된 카제인의 반응으로 얻은 4급 암모늄클로라이드이다.",
        "INGR_SYNONYM": "하이드록시프로필트리모늄하이드롤라이즈드카제인"
      },
      {
        "INGR_KOR_NAME": "포타슘코코일하이드롤라이즈드카제인",
        "INGR_ENG_NAME": "Potassium Cocoyl Hydrolyzed Casein",
        "CAS_NO": null,
        "ORIGIN_MAJOR_KOR_NAME": "이 원료는 코코넛애씨드클로라이드와 하이드롤라이즈드카제인으로 이루어진 축합물의 포타슘염이다.",
        "INGR_SYNONYM": null
      }
    ]
  }
}
```

---

### 2. 식품 원재료 동의어

`https://www.data.go.kr/data/15058665/openapi.do#`

-- 출력 예시 | 검색어: 카제인 --
```json
{
  "header": {
    "resultCode": "00",
    "resultMsg": "NORMAL SERVICE."
  },
  "body": {
    "pageNo": 1,
    "totalCount": 9,
    "numOfRows": 3,
    "items": [
      {
        "LCLAS_NM": "식품원료(A코드)",
        "MLSFC_NM": "기타",
        "RPRSNT_RAWMTRL_NM": "카제인포스포펩타이드",
        "RAWMTRL_NCKNM": " ",
        "ENG_NM": "CPP(Casein Phosphopeptide)",
        "SCNM": null,
        "REGN_CD_NM": "-",
        "RAWMTRL_STATS_CD_NM": null,
        "USE_CND_NM": null
      },
      {
        "LCLAS_NM": "식품첨가물(B코드)",
        "MLSFC_NM": "식품첨가물",
        "RPRSNT_RAWMTRL_NM": "카제인나트륨",
        "RAWMTRL_NCKNM": "카제인Na,카제인Na,카제인나트률,카제인나트륨분말가루",
        "ENG_NM": "Sodium Caseinate",
        "SCNM": null,
        "REGN_CD_NM": "-",
        "RAWMTRL_STATS_CD_NM": null,
        "USE_CND_NM": null
      },
      {
        "LCLAS_NM": "식품첨가물(B코드)",
        "MLSFC_NM": "식품첨가물",
        "RPRSNT_RAWMTRL_NM": "카제인칼슘",
        "RAWMTRL_NCKNM": null,
        "ENG_NM": "Calcium caseinate",
        "SCNM": null,
        "REGN_CD_NM": "-",
        "RAWMTRL_STATS_CD_NM": null,
        "USE_CND_NM": null
      }
    ]
  }
}
```

---

### 3. 식품등의 표시기준 [ 법령 ]

`https://www.law.go.kr/LSW/admRulLsInfoP.do?admRulId=36814&efYd=0#AJAX`

최하단부 별표 4, 5, 6 성분 별 간략명 수집에 활용 가능

-- 예시 --

| 명칭 | 간략명 | 주용도 |
| :---: | :---: | :---: |
| 카제인나트륨 | 카제인Na | 유화제, 증점제, 안정제 |