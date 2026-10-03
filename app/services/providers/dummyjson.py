import httpx
from pydantic import ValidationError
from app.schemas.product import ProviderProduct, SearchResult
from app.services.providers.base import ProductProvider, ProviderError, ProductNotFound

class DummyJsonProvider(ProductProvider):
    source = "dummyjson"
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def _get(self, path: str, params: dict | None = None) -> dict:
        try:
            response = await self.client.get("https://dummyjson.com" + path, params=params)
            if response.status_code == 404:
                raise ProductNotFound("Product not found at provider")
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError("Product provider is unavailable; try again later") from exc

    async def get_product(self, product_id: int) -> ProviderProduct:
        data = await self._get(f"/products/{product_id}")
        try:
            return ProviderProduct.model_validate(data)
        except ValidationError as exc:
            raise ProviderError("Invalid product provider response") from exc

    async def search(self, query: str, limit: int = 12, skip: int = 0) -> SearchResult:
        path = "/products/search" if query else "/products"
        data = await self._get(path, {"q": query, "limit": limit, "skip": skip})
        try:
            return SearchResult.model_validate(data)
        except ValidationError as exc:
            raise ProviderError("Invalid product provider response") from exc
