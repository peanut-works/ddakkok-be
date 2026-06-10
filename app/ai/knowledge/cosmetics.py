"""영유아 화장품 주의 성분 지식 청크.

근거: 화장품 안전기준 등에 관한 규정 (식약처 고시)
     영유아용 화장품 안전사용 가이드 (식약처, 2022)
"""

COSMETICS_CHUNKS: list[dict[str, str]] = [
    {
        "title": "파라벤류 보존제 (영유아 주의)",
        "content": (
            "파라벤(Paraben)은 화장품의 세균·곰팡이 오염을 막는 보존제입니다. "
            "프로필파라벤(Propylparaben)·이소부틸파라벤(Isobutylparaben)·이소프로필파라벤은 "
            "내분비 교란 가능성이 있어 영유아용 제품에는 0.14% 이하로 규제됩니다(EU 기준). "
            "한국 식약처는 3세 이하 영유아용 제품에 프로필파라벤·부틸파라벤 사용을 금지했습니다. "
            "성분표에 'propylparaben', 'butylparaben', 'isopropylparaben', 'isobutylparaben' 확인이 필요합니다."
        ),
        "category": "cosmetics_preservative",
        "source": "화장품 안전기준 등에 관한 규정 (식약처 고시 제2023-3호)",
    },
    {
        "title": "페녹시에탄올 (Phenoxyethanol) 함량 주의",
        "content": (
            "페녹시에탄올은 파라벤 대체 보존제로 광범위하게 사용됩니다. "
            "한국·EU 기준 최대 허용 농도는 1.0%이며, 이 농도에서 영유아 피부 자극이 보고된 사례가 있습니다. "
            "프랑스 ANSM은 3세 미만 영아의 기저귀 부위·점막 접촉 제품에 주의를 권고했습니다. "
            "성분표에 'phenoxyethanol', '페녹시에탄올' 표기를 확인하세요."
        ),
        "category": "cosmetics_preservative",
        "source": "화장품 안전기준 등에 관한 규정 / ANSM 권고문",
    },
    {
        "title": "향료 및 착향제 (영유아 무향 권장)",
        "content": (
            "향료는 영유아 피부 자극·알레르기 유발의 주요 원인입니다. "
            "식약처는 영유아용 화장품에 무향(fragrance-free) 또는 저자극 향료 사용을 권장합니다. "
            "'Fragrance', 'Parfum'으로 표기된 성분은 수십~수백 가지 화학물질의 혼합물일 수 있습니다. "
            "아토피 피부염·민감성 피부 영유아에게는 무향 제품 사용을 강력히 권장합니다."
        ),
        "category": "cosmetics_irritant",
        "source": "영유아용 화장품 안전사용 가이드 (식약처, 2022)",
    },
    {
        "title": "포름알데히드 방출 보존제",
        "content": (
            "일부 보존제는 서서히 포름알데히드를 방출하여 피부 자극·알레르기를 유발합니다. "
            "해당 성분: DMDM 하이단토인(DMDM Hydantoin), 이미다졸리디닐우레아(Imidazolidinyl Urea), "
            "디아졸리디닐우레아(Diazolidinyl Urea), 쿼터늄-15(Quaternium-15), "
            "브로노폴(Bronopol, 2-bromo-2-nitropropane-1,3-diol). "
            "포름알데히드 자체는 영유아용 화장품 사용 금지 성분입니다."
        ),
        "category": "cosmetics_preservative",
        "source": "화장품 안전기준 등에 관한 규정 별표 1 사용금지 원료",
    },
    {
        "title": "미네랄 오일 및 석유계 성분",
        "content": (
            "미네랄 오일(Mineral Oil), 파라핀(Paraffinum Liquidum), 페트롤라텀(Petrolatum)은 "
            "석유 정제 부산물로 영유아 피부에 피막을 형성합니다. "
            "정제 등급이 낮은 경우 PAH(다환방향족탄화수소) 불순물이 포함될 수 있어 EU는 영유아 제품에 "
            "고순도 정제 미네랄 오일만 허용합니다. "
            "'mineral oil', 'paraffinum liquidum', 'petrolatum', 'white petrolatum' 성분을 확인하세요."
        ),
        "category": "cosmetics_base",
        "source": "화장품 안전기준 등에 관한 규정",
    },
    {
        "title": "계면활성제 SLS·SLES (자극성)",
        "content": (
            "소듐라우릴설페이트(SLS, Sodium Lauryl Sulfate)는 강한 세정력으로 영유아 피부 장벽을 손상시킬 수 있습니다. "
            "소듐라우레스설페이트(SLES, Sodium Laureth Sulfate)는 1,4-다이옥산 잔류 우려가 있습니다. "
            "영유아용 샴푸·바디워시에는 '순한' 계면활성제(코코일글루타메이트 등) 사용을 권장합니다. "
            "성분표 앞부분에 'sodium lauryl sulfate', 'sodium laureth sulfate'가 있으면 주의가 필요합니다."
        ),
        "category": "cosmetics_surfactant",
        "source": "영유아용 화장품 안전사용 가이드 (식약처, 2022)",
    },
    {
        "title": "에센셜 오일 (영유아 사용 금지/주의)",
        "content": (
            "페퍼민트 오일(Peppermint Oil)은 주성분 멘톨이 영아 호흡 억제를 유발할 수 있어 "
            "2세 이하 사용이 금지됩니다. "
            "티트리 오일(Tea Tree Oil)은 피부 자극·알레르기 유발 성분으로 영유아 제품에 권장되지 않습니다. "
            "유칼립투스 오일(Eucalyptus Oil)도 2세 미만에게 유해할 수 있습니다. "
            "'menthol', 'peppermint oil', 'tea tree oil', 'eucalyptus oil', 'camphor' 성분을 확인하세요."
        ),
        "category": "cosmetics_essential_oil",
        "source": "화장품 안전기준 등에 관한 규정 / 미국소아과학회(AAP) 권고",
    },
    {
        "title": "옥시벤존·화학 자외선 차단제 (영유아 주의)",
        "content": (
            "옥시벤존(Oxybenzone, Benzophenone-3)은 피부 흡수 후 내분비 교란 가능성이 제기됩니다. "
            "미국소아과학회(AAP)는 6개월 미만 영아에게는 자외선 차단제 사용을 금지하고, "
            "6개월~2세는 징크옥사이드·티타늄다이옥사이드 기반의 물리적 자외선 차단제만 권장합니다. "
            "'oxybenzone', 'benzophenone-3', 'octinoxate', 'avobenzone' 성분이 있는 제품은 영아에게 사용 금지입니다."
        ),
        "category": "cosmetics_sunscreen",
        "source": "AAP Clinical Report 2019 / 식약처 자외선차단제 안전정보",
    },
    {
        "title": "탈크 (Talc) — 석면 불순물 주의",
        "content": (
            "탈크(Talc)는 베이비파우더·파우더 파운데이션에 사용되는 광물성 성분입니다. "
            "불순물로 석면(asbestos)이 포함될 수 있어 영유아 흡입 노출 시 호흡기 위험이 있습니다. "
            "미국 FDA는 석면 불순물이 없는 '코스메틱 그레이드' 탈크만 허용하지만, "
            "영아에게는 분말 제형 사용 자체를 자제하도록 권고합니다. "
            "성분표에 'talc', 'talcum', '탈크' 표기를 확인하세요."
        ),
        "category": "cosmetics_base",
        "source": "미국 FDA 탈크 안전정보 / 식약처 베이비파우더 안전관리",
    },
]
