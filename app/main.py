from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.orm import Session

from app import cache, crud, schemas
from app.db import Base, engine, get_db
from app.models import Status
from app.rate_limit import limiter


@asynccontextmanager
async def lifespan(_: FastAPI):
    # для учебного проекта достаточно; в проде сюда встанет alembic upgrade head
    Base.metadata.create_all(engine)
    yield
    await cache.close_client()


app = FastAPI(
    title="Job Tracker",
    description="Трекер откликов на вакансии и заказы по площадкам.",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get("/health", tags=["service"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/platforms", response_model=schemas.PlatformRead, status_code=201, tags=["platforms"])
@limiter.limit("15/minute")
async def create_platform(
    request: Request, payload: schemas.PlatformCreate, db: Session = Depends(get_db)
):
    if crud.get_platform_by_name(db, payload.name):
        raise HTTPException(409, "Площадка с таким названием уже есть")
    platform = crud.create_platform(db, payload)
    await cache.invalidate("platforms:list")
    return platform


@app.get("/platforms", response_model=list[schemas.PlatformRead], tags=["platforms"])
@limiter.limit("60/minute")
async def list_platforms(request: Request, db: Session = Depends(get_db)):
    return await crud.list_platforms_cached(db)


@app.post(
    "/applications", response_model=schemas.ApplicationRead, status_code=201, tags=["applications"]
)
@limiter.limit("15/minute")
async def create_application(
    request: Request, payload: schemas.ApplicationCreate, db: Session = Depends(get_db)
):
    if crud.get_platform(db, payload.platform_id) is None:
        raise HTTPException(404, "Площадка не найдена")
    application = crud.create_application(db, payload)
    await crud.invalidate_application_caches()
    return application


@app.get("/applications", response_model=list[schemas.ApplicationRead], tags=["applications"])
@limiter.limit("60/minute")
async def list_applications(
    request: Request,
    status: Status | None = None,
    platform_id: int | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    return await crud.list_applications_cached(
        db, status=status, platform_id=platform_id, limit=limit, offset=offset
    )


@app.get(
    "/applications/{application_id}", response_model=schemas.ApplicationRead, tags=["applications"]
)
@limiter.limit("60/minute")
async def get_application(request: Request, application_id: int, db: Session = Depends(get_db)):
    obj = crud.get_application(db, application_id)
    if obj is None:
        raise HTTPException(404, "Отклик не найден")
    return obj


@app.patch(
    "/applications/{application_id}", response_model=schemas.ApplicationRead, tags=["applications"]
)
@limiter.limit("15/minute")
async def update_application(
    request: Request,
    application_id: int,
    payload: schemas.ApplicationUpdate,
    db: Session = Depends(get_db),
):
    obj = crud.get_application(db, application_id)
    if obj is None:
        raise HTTPException(404, "Отклик не найден")
    updated = crud.update_application(db, obj, payload)
    await crud.invalidate_application_caches()
    return updated


@app.post(
    "/applications/{application_id}/status",
    response_model=schemas.ApplicationRead,
    tags=["applications"],
)
@limiter.limit("15/minute")
async def change_status(
    request: Request,
    application_id: int,
    payload: schemas.StatusChange,
    db: Session = Depends(get_db),
):
    obj = crud.get_application(db, application_id)
    if obj is None:
        raise HTTPException(404, "Отклик не найден")
    updated = crud.change_status(db, obj, payload.status, payload.comment)
    await crud.invalidate_application_caches()
    return updated


@app.delete("/applications/{application_id}", status_code=204, tags=["applications"])
@limiter.limit("15/minute")
async def delete_application(
    request: Request, application_id: int, db: Session = Depends(get_db)
):
    obj = crud.get_application(db, application_id)
    if obj is None:
        raise HTTPException(404, "Отклик не найден")
    crud.delete_application(db, obj)
    await crud.invalidate_application_caches()


@app.get("/stats", response_model=list[schemas.StatsRow], tags=["stats"])
@limiter.limit("20/minute")
async def stats(request: Request, db: Session = Depends(get_db)):
    return await crud.stats_cached(db)
