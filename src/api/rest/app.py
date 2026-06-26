from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from src.api.rest.middleware.cors import add_cors_middleware
from src.api.rest.middleware.error_handler import add_error_handlers
from src.api.rest.routes.extractions import (
    router as extractions_router,
)
from src.api.rest.routes.gmail_monitoring import (
    router as gmail_monitoring_router,
)
from src.api.rest.routes.gmail_webhook import (
    router as gmail_webhook_router,
)
from src.api.rest.routes.health import router as health_router
from src.api.rest.routes.invoices import (
    router as invoices_router,
)
from src.api.rest.routes.purchase_order import (
    router as purchase_order_router,
)
from src.data.clients.postgres_client import (
    get_or_create_engine,
    get_session_factory,
)
from src.core.services.gmail_startup_service import (
    resume_active_monitoring,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    engine = get_or_create_engine()

    # Startup
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))

        print("Database connected")

        session_factory = get_session_factory()

        async with session_factory() as session:
            await resume_active_monitoring(
                session,
            )

    except Exception as e:
        print("Database connection failed")
        print(e)

    yield

    # Shutdown
    await engine.dispose()

    print("Database connections closed")


app = FastAPI(
    title="PayU",
    lifespan=lifespan,
)

add_cors_middleware(app)
add_error_handlers(app)

app.include_router(router=health_router)
app.include_router(router=gmail_monitoring_router)
app.include_router(router=gmail_webhook_router)
app.include_router(router=purchase_order_router)
app.include_router(router=invoices_router)
app.include_router(router=extractions_router)
