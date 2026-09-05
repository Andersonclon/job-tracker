from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy.orm import Session

from app import crud, schemas
from app.db import Base, engine, get_db
from app.models import Status


@asynccontextmanager
async def lifespan(_: FastAPI):
    # для учебного проекта достаточно; в проде сюда встанет alembic upgrade head
    Base.metadata.create_all(engine)
    yield


app = FastAPI(
    title="Job Tracker",
    description="Трекер откликов на вакансии и заказы по площадкам.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["service"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/platforms", response_model=schemas.PlatformRead, status_code=201, tags=["platforms"])
def create_platform(payload: schemas.PlatformCreate, db: Session = Depends(get_db)):
    if crud.get_platform_by_name(db, payload.name):
        raise HTTPException(409, "Площадка с таким названием уже есть")
    return crud.create_platform(db, payload)


@app.get("/platforms", response_model=list[schemas.PlatformRead], tags=["platforms"])
def list_platforms(db: Session = Depends(get_db)):
    return crud.list_platforms(db)


@app.post(
    "/applications", response_model=schemas.ApplicationRead, status_code=201, tags=["applications"]
)
def create_application(payload: schemas.ApplicationCreate, db: Session = Depends(get_db)):
    if crud.get_platform(db, payload.platform_id) is None:
        raise HTTPException(404, "Площадка не найдена")
    return crud.create_application(db, payload)


@app.get("/applications", response_model=list[schemas.ApplicationRead], tags=["applications"])
def list_applications(
    status: Status | None = None,
    platform_id: int | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    return crud.list_applications(
        db, status=status, platform_id=platform_id, limit=limit, offset=offset
    )


@app.get(
    "/applications/{application_id}", response_model=schemas.ApplicationRead, tags=["applications"]
)
def get_application(application_id: int, db: Session = Depends(get_db)):
    obj = crud.get_application(db, application_id)
    if obj is None:
        raise HTTPException(404, "Отклик не найден")
    return obj


@app.patch(
    "/applications/{application_id}", response_model=schemas.ApplicationRead, tags=["applications"]
)
def update_application(
    application_id: int, payload: schemas.ApplicationUpdate, db: Session = Depends(get_db)
):
    obj = crud.get_application(db, application_id)
    if obj is None:
        raise HTTPException(404, "Отклик не найден")
    return crud.update_application(db, obj, payload)


@app.post(
    "/applications/{application_id}/status",
    response_model=schemas.ApplicationRead,
    tags=["applications"],
)
def change_status(
    application_id: int, payload: schemas.StatusChange, db: Session = Depends(get_db)
):
    obj = crud.get_application(db, application_id)
    if obj is None:
        raise HTTPException(404, "Отклик не найден")
    return crud.change_status(db, obj, payload.status, payload.comment)


@app.delete("/applications/{application_id}", status_code=204, tags=["applications"])
def delete_application(application_id: int, db: Session = Depends(get_db)):
    obj = crud.get_application(db, application_id)
    if obj is None:
        raise HTTPException(404, "Отклик не найден")
    crud.delete_application(db, obj)


@app.get("/stats", response_model=list[schemas.StatsRow], tags=["stats"])
def stats(db: Session = Depends(get_db)):
    return crud.platform_stats(db)
