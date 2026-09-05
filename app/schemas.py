from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models import Status


class PlatformCreate(BaseModel):
    name: str
    url: str | None = None


class PlatformRead(PlatformCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int


class ApplicationCreate(BaseModel):
    platform_id: int
    company: str
    position: str
    url: str | None = None
    salary: str | None = None
    sent_at: date | None = None
    notes: str | None = None


class ApplicationUpdate(BaseModel):
    company: str | None = None
    position: str | None = None
    salary: str | None = None
    notes: str | None = None


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: Status
    comment: str | None
    happened_at: datetime


class ApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform_id: int
    company: str
    position: str
    url: str | None
    salary: str | None
    status: Status
    sent_at: date
    notes: str | None
    events: list[EventRead] = []


class StatusChange(BaseModel):
    status: Status
    comment: str | None = None


class StatsRow(BaseModel):
    platform: str
    total: int
    responded: int
