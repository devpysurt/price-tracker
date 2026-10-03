from datetime import datetime
from decimal import Decimal
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

Price = Annotated[Decimal, Field(ge=0, le=999999999, max_digits=11, decimal_places=2)]

class ProductInput(BaseModel):
    external_id: int = Field(gt=0)
    target_price: Price

class TargetInput(BaseModel):
    target_price: Price

class ProviderProduct(BaseModel):
    id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=300)
    thumbnail: HttpUrl
    price: Price

class SearchResult(BaseModel):
    products: list[ProviderProduct]
    total: int
    skip: int
    limit: int

class HistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int
    price: Decimal
    checked_at: datetime

class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    external_id: int
    title: str
    thumbnail: str
    source: str
    current_price: Decimal
    target_price: Decimal
    created_at: datetime
    updated_at: datetime
    last_checked_at: datetime
    notification_sent: bool
    minimum_price: Decimal
    maximum_price: Decimal
    first_price: Decimal
    absolute_change: Decimal
    percentage_change: Decimal | None
