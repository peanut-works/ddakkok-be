from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class ProductLabelTextParseRequest(BaseModel):
    text: str = Field(
        ...,
        examples=[
            (
                "제품명: 밀크 프로틴 보습 물티슈\n"
                "제조사: 해커톤생활건강\n"
                "성분: 정제수, 글리세린, 카제인Na, 페녹시에탄올\n"
                "유통기한: 2027.08.31"
            )
        ],
    )
    category: str = Field(..., examples=["WET_TISSUE"])


class ProductLabelTextParseResponse(BaseModel):
    name: str | None = None
    category: str
    manufacturer: str | None = None
    expiry_date: date | None = None
    raw_ingredients_text: str | None = None
    ingredients: list[str] = Field(default_factory=list)
    normalized_ingredients: list[str] = Field(default_factory=list)
    ocr_raw_text: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "밀크 프로틴 보습 물티슈",
                "category": "WET_TISSUE",
                "manufacturer": "해커톤생활건강",
                "expiry_date": "2027-08-31",
                "raw_ingredients_text": "정제수, 글리세린, 카제인Na, 페녹시에탄올",
                "ingredients": ["정제수", "글리세린", "카제인Na", "페녹시에탄올"],
                "normalized_ingredients": ["정제수", "글리세린", "카제인나트륨", "페녹시에탄올"],
                "ocr_raw_text": (
                    "제품명: 밀크 프로틴 보습 물티슈\n"
                    "제조사: 해커톤생활건강\n"
                    "성분: 정제수, 글리세린, 카제인Na, 페녹시에탄올\n"
                    "유통기한: 2027.08.31"
                ),
            }
        }
    )


class ProductCreateRequest(BaseModel):
    name: str = Field(..., examples=["A 브랜드 물티슈"])
    category: str = Field(..., examples=["WET_TISSUE"])
    manufacturer: str | None = Field(default=None, examples=["A제조사"])
    barcode: str | None = Field(default=None, examples=["880000000001"])
    expiry_date: date | None = Field(default=None, examples=["2027-03-15"])
    raw_ingredients_text: str | None = Field(
        default=None,
        examples=["정제수, 글리세린, 카제인나트륨, 페녹시에탄올"],
    )
    ingredients: list[str] = Field(
        default_factory=list,
        examples=[["정제수", "글리세린", "카제인나트륨", "페녹시에탄올"]],
    )
    normalized_ingredients: list[str] | None = Field(
        default=None,
        examples=[["정제수", "글리세린", "카제인나트륨", "페녹시에탄올"]],
    )
    image_url: str | None = None
    ocr_raw_text: str | None = None


class ProductResponse(BaseModel):
    id: int
    facility_id: int
    name: str
    category: str
    manufacturer: str | None = None
    barcode: str | None = None
    expiry_date: date | None = None
    raw_ingredients_text: str | None = None
    ingredients: list[str] = Field(default_factory=list)
    normalized_ingredients: list[str] = Field(default_factory=list)
    image_url: str | None = None
    ocr_raw_text: str | None = None
    created_by_id: int | None = None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "facility_id": 1,
                "name": "A 브랜드 물티슈",
                "category": "WET_TISSUE",
                "manufacturer": "A제조사",
                "barcode": "880000000001",
                "expiry_date": "2027-03-15",
                "raw_ingredients_text": "정제수, 글리세린, 카제인나트륨, 페녹시에탄올",
                "ingredients": ["정제수", "글리세린", "카제인나트륨", "페녹시에탄올"],
                "normalized_ingredients": ["정제수", "글리세린", "카제인나트륨", "페녹시에탄올"],
                "image_url": None,
                "ocr_raw_text": None,
                "created_by_id": 1,
            }
        },
    )
