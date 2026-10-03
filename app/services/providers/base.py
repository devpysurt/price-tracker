from abc import ABC, abstractmethod
from app.schemas.product import ProviderProduct, SearchResult

class ProviderError(Exception):
    pass

class ProductNotFound(ProviderError):
    pass

class ProductProvider(ABC):
    source: str
    @abstractmethod
    async def get_product(self, product_id: int) -> ProviderProduct:
        ...
    @abstractmethod
    async def search(self, query: str, limit: int, skip: int) -> SearchResult:
        ...
