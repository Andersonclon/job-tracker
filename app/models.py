import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Status(enum.StrEnum):
    sent = "sent"
    viewed = "viewed"
    invited = "invited"
    interview = "interview"
    offer = "offer"
    rejected = "rejected"
    no_response = "no_response"


# один общий тип на две таблицы, иначе CREATE TYPE выполнится дважды
status_enum = Enum(Status, name="application_status", metadata=Base.metadata)


class Platform(Base):
    """Площадка: hh.ru, Профи.ру, Хабр Карьера, прямой контакт и т.д."""

    __tablename__ = "platforms"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    url: Mapped[str | None] = mapped_column(String(255))

    applications: Mapped[list["Application"]] = relationship(
        back_populates="platform", cascade="all, delete-orphan"
    )


class Application(Base):
    """Один отклик на вакансию или заказ."""

    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    platform_id: Mapped[int] = mapped_column(
        ForeignKey("platforms.id", ondelete="CASCADE"), index=True
    )
    company: Mapped[str] = mapped_column(String(128))
    position: Mapped[str] = mapped_column(String(128))
    url: Mapped[str | None] = mapped_column(String(500))
    salary: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[Status] = mapped_column(status_enum, default=Status.sent, index=True)
    sent_at: Mapped[date] = mapped_column(Date, default=date.today)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    platform: Mapped[Platform] = relationship(back_populates="applications")
    events: Mapped[list["Event"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="Event.happened_at",
    )


class Event(Base):
    """История смены статусов по отклику."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[Status] = mapped_column(status_enum)
    comment: Mapped[str | None] = mapped_column(Text)
    happened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    application: Mapped[Application] = relationship(back_populates="events")
