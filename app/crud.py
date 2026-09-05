from datetime import date

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from app import schemas
from app.models import Application, Event, Platform, Status

# статусы, которые означают, что работодатель как-то отреагировал
RESPONSE_STATUSES = (Status.invited, Status.interview, Status.offer, Status.rejected)


def get_platform(db: Session, platform_id: int) -> Platform | None:
    return db.get(Platform, platform_id)


def get_platform_by_name(db: Session, name: str) -> Platform | None:
    return db.scalar(select(Platform).where(Platform.name == name))


def list_platforms(db: Session) -> list[Platform]:
    return list(db.scalars(select(Platform).order_by(Platform.name)))


def create_platform(db: Session, payload: schemas.PlatformCreate) -> Platform:
    obj = Platform(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def get_application(db: Session, application_id: int) -> Application | None:
    stmt = (
        select(Application)
        .options(selectinload(Application.events))
        .where(Application.id == application_id)
    )
    return db.scalar(stmt)


def list_applications(
    db: Session,
    *,
    status: Status | None = None,
    platform_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Application]:
    stmt = select(Application).options(selectinload(Application.events))
    if status is not None:
        stmt = stmt.where(Application.status == status)
    if platform_id is not None:
        stmt = stmt.where(Application.platform_id == platform_id)
    stmt = stmt.order_by(Application.sent_at.desc(), Application.id.desc())
    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt))


def create_application(db: Session, payload: schemas.ApplicationCreate) -> Application:
    data = payload.model_dump()
    data["sent_at"] = data.get("sent_at") or date.today()
    obj = Application(**data, status=Status.sent)
    obj.events.append(Event(status=Status.sent, comment="Отклик отправлен"))
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_application(
    db: Session, obj: Application, payload: schemas.ApplicationUpdate
) -> Application:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


def change_status(
    db: Session, obj: Application, new_status: Status, comment: str | None = None
) -> Application:
    obj.status = new_status
    obj.events.append(Event(status=new_status, comment=comment))
    db.commit()
    db.refresh(obj)
    return obj


def delete_application(db: Session, obj: Application) -> None:
    db.delete(obj)
    db.commit()


def platform_stats(db: Session) -> list[dict]:
    """Сколько откликов ушло по каждой площадке и сколько дали реакцию."""
    stmt = (
        select(
            Platform.name.label("platform"),
            func.count(Application.id).label("total"),
            func.count(
                case((Application.status.in_(RESPONSE_STATUSES), 1))
            ).label("responded"),
        )
        .join(Application, Application.platform_id == Platform.id)
        .group_by(Platform.name)
        .order_by(func.count(Application.id).desc())
    )
    return [dict(row._mapping) for row in db.execute(stmt)]
