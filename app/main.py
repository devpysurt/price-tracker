import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.api.routes import router
from app.config import Settings
from app.database import Base, make_database
from app.services.notifications import ConsoleNotificationService, NotificationService
from app.services.price_tracker import PriceTracker, TrackedNotFound, AlreadyTracked
from app.services.providers.base import ProductProvider, ProviderError, ProductNotFound
from app.services.providers.dummyjson import DummyJsonProvider

ROOT = Path(__file__).parent
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

def create_app(settings: Settings | None = None, provider: ProductProvider | None = None,
               notifications: NotificationService | None = None) -> FastAPI:
    config = settings or Settings()
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine, sessions = make_database(config.database_url)
        Base.metadata.create_all(engine)
        async with httpx.AsyncClient(timeout=10.0) as client:
            tracker = PriceTracker(sessions, provider or DummyJsonProvider(client),
                                   notifications or ConsoleNotificationService(), config)
            app.state.tracker = tracker
            scheduler = AsyncIOScheduler(timezone="UTC")
            app.state.scheduler = scheduler
            if config.scheduler_enabled:
                scheduler.add_job(tracker.refresh_all, "interval",
                    seconds=config.price_check_interval_seconds, id="price-refresh",
                    max_instances=1, coalesce=True, misfire_grace_time=30)
                scheduler.start()
            try:
                yield
            finally:
                if scheduler.running:
                    scheduler.shutdown(wait=False)
                    await asyncio.sleep(0)  # Let the scheduler cancel jobs before closing resources.
                engine.dispose()

    app = FastAPI(title=config.app_name, version="1.0.0", lifespan=lifespan,
                  description="A single-user price tracker. Monetary values are decimal strings in USD.")
    app.include_router(router)
    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    templates = Jinja2Templates(directory=ROOT / "templates")

    async def domain_error(request: Request, exc: Exception):
        status = 404 if isinstance(exc, (TrackedNotFound, ProductNotFound)) else 409 if isinstance(exc, AlreadyTracked) else 502
        return JSONResponse(status_code=status, content={"detail": str(exc)})
    for exception in (TrackedNotFound, AlreadyTracked, ProviderError, ProductNotFound):
        app.add_exception_handler(exception, domain_error)

    @app.get("/", include_in_schema=False)
    async def index(request: Request):
        return templates.TemplateResponse(request=request, name="index.html", context={"simulation": config.simulate_price_changes})

    @app.get("/products/{product_id}", include_in_schema=False)
    async def product(request: Request, product_id: int):
        tracked = request.app.state.tracker.get(product_id)
        return templates.TemplateResponse(request=request, name="product.html", context={
            "product": tracked, "simulation": config.simulate_price_changes})
    return app

app = create_app()
