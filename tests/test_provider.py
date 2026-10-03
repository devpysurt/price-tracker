import httpx
import pytest
from app.services.providers.dummyjson import DummyJsonProvider
from app.services.providers.base import ProviderError, ProductNotFound

async def test_provider_search_and_get():
    def handler(request):
        item = {"id":1,"title":"Phone","price":99.99,"thumbnail":"https://example.com/a.png"}
        if request.url.path == "/products/1":
            return httpx.Response(200,json=item)
        assert request.url.path == "/products/search"
        assert request.url.params["q"] == "phone"
        return httpx.Response(200,json={"products":[item],"total":1,"skip":0,"limit":12})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = DummyJsonProvider(client)
        assert str((await provider.get_product(1)).price) == "99.99"
        assert (await provider.search("phone",12,0)).total == 1

@pytest.mark.parametrize("status,error", [(404,ProductNotFound),(429,ProviderError),(503,ProviderError)])
async def test_http_errors(status,error):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(status))) as client:
        with pytest.raises(error):
            await DummyJsonProvider(client).get_product(1)

async def test_malformed_response():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={"price":"bad"}))) as client:
        with pytest.raises(ProviderError):
            await DummyJsonProvider(client).get_product(1)

async def test_timeout():
    def handler(request):
        raise httpx.ReadTimeout("timeout",request=request)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderError):
            await DummyJsonProvider(client).get_product(1)
