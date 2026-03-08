import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from core.database import Base


class TenantStatus(str, enum.Enum):
    ACTIVE = "active"
    DISABLED = "disabled"


class ReportJobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Tenant(Base):
    """A company or organization and all its users for the application."""

    __tablename__ = "tenant"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    external_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    shard_id: Mapped[int] = mapped_column(nullable=False, default=0)
    status: Mapped[TenantStatus] = mapped_column(
        Enum(TenantStatus, name="tenant_status"),
        nullable=False,
        default=TenantStatus.ACTIVE,
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    api_keys: Mapped[list["ApiKey"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
    events: Mapped[list["Event"]] = relationship(back_populates="tenant")
    daily_aggregates: Mapped[list["DailyAggregate"]] = relationship(
        back_populates="tenant"
    )
    report_jobs: Mapped[list["ReportJob"]] = relationship(back_populates="tenant")


class EventType(Base):
    """Catalog of allowed event kinds"""

    __tablename__ = "event_type"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    events: Mapped[list["Event"]] = relationship(back_populates="event_type")
    daily_aggregates: Mapped[list["DailyAggregate"]] = relationship(
        back_populates="event_type"
    )


class ApiKey(Base):
    __tablename__ = "api_key"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_used_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    tenant: Mapped["Tenant"] = relationship(back_populates="api_keys")
    __table_args__ = (Index("ix_api_key_tenant_id", "tenant_id"),)


class Event(Base):
    """An action that a client has taken in the application."""

    __tablename__ = "event"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant.id"),
        nullable=False,
    )
    event_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("event_type.id"),
        nullable=False,
    )
    entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    payload_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    tenant: Mapped["Tenant"] = relationship(back_populates="events")
    event_type: Mapped["EventType"] = relationship(back_populates="events")

    __table_args__ = (
        Index("ix_event_tenant_occurred_at", "tenant_id", "occurred_at"),
        Index(
            "ix_event_tenant_type_occurred_at",
            "tenant_id",
            "event_type_id",
            "occurred_at",
        ),
        Index("ix_event_occurred_at", "occurred_at"),
    )


class DailyAggregate(Base):
    __tablename__ = "daily_aggregate"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant.id"),
        nullable=False,
    )
    event_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("event_type.id"),
        nullable=False,
    )
    aggregate_date: Mapped[date] = mapped_column(Date, nullable=False)
    event_count: Mapped[int] = mapped_column(nullable=False, default=0)

    tenant: Mapped["Tenant"] = relationship(back_populates="daily_aggregates")
    event_type: Mapped["EventType"] = relationship(back_populates="daily_aggregates")

    __table_args__ = (
        PrimaryKeyConstraint(
            "tenant_id", "event_type_id", "aggregate_date", name="pk_daily_aggregates"
        ),
    )


class ReportJob(Base):
    __tablename__ = "report_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant.id"),
        nullable=False,
    )
    report_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[ReportJobStatus] = mapped_column(
        Enum(ReportJobStatus, name="report_job_status"),
        nullable=False,
        default=ReportJobStatus.PENDING,
    )
    parameters_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    result_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="report_jobs")

    __table_args__ = (
        Index("ix_report_job_tenant_requested_at", "tenant_id", "requested_at"),
    )
