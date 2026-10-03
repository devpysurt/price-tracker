from typing import Annotated
from fastapi import APIRouter, Depends, Query, Request, Response
from app.schemas.product import ProductInput, TargetInput, ProductOut, HistoryOut, SearchResult
from app.services.price_tracker import PriceTracker

router = APIRouter(prefix="/api")
def get_tracker(request: Request) -> PriceTracker:
    return request.app.state.tracker
Tracker = Annotated[PriceTracker, Depends(get_tracker)]

@router.get("/health", tags=["Health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}

@router.get("/products/search", response_model=SearchResult, tags=["Catalog"])
async def search(tracker: Tracker, q: str = Query("", max_length=200),
                 limit: int = Query(12, ge=1, le=100), skip: int = Query(0, ge=0)):
    return await tracker.provider.search(q.strip(), limit, skip)

@router.post("/tracked", response_model=ProductOut, status_code=201, tags=["Tracking"])
async def add(data: ProductInput, tracker: Tracker):
    return await tracker.add(data.external_id, data.target_price)

@router.get("/tracked", response_model=list[ProductOut], tags=["Tracking"])
async def list_tracked(tracker: Tracker):
    return tracker.list_tracked()

@router.get("/tracked/{product_id}", response_model=ProductOut, tags=["Tracking"])
async def get(product_id: int, tracker: Tracker):
    return tracker.get(product_id)

@router.get("/tracked/{product_id}/history", response_model=list[HistoryOut], tags=["Tracking"])
async def history(product_id: int, tracker: Tracker):
    return tracker.history(product_id)

@router.post("/tracked/{product_id}/refresh", response_model=ProductOut, tags=["Tracking"])
async def refresh(product_id: int, tracker: Tracker):
    return await tracker.refresh(product_id)

@router.patch("/tracked/{product_id}", response_model=ProductOut, tags=["Tracking"])
async def patch(product_id: int, data: TargetInput, tracker: Tracker):
    return await tracker.update_target(product_id, data.target_price)

@router.delete("/tracked/{product_id}", status_code=204, tags=["Tracking"])
async def delete(product_id: int, tracker: Tracker):
    await tracker.delete(product_id)
    return Response(status_code=204)
