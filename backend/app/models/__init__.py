"""ORM modelleri — şartname Bölüm 6'daki veri modeli.

Bu modül tüm model modüllerini içeri alır. Alembic `Base.metadata`'yı buradan
okuyor; bir modül burada listelenmezse tabloları görünmez olur ve autogenerate
onları "silinmiş" sayar.
"""

from app.models.base import Base, IdMixin, TimestampMixin
from app.models.company import Company
from app.models.enums import (
    AttendanceStatus,
    EventStatus,
    JobStatus,
    LayoutMode,
    MeetingRequestStatus,
    PlanStatus,
    RegistrationStatus,
    TableKind,
    TagDirection,
)
from app.models.event import Event
from app.models.layout import Layout, LayoutArea, Table
from app.models.plan import Assignment, MatchReason, Plan
from app.models.profile import Profile, ProfileTag
from app.models.registration import MeetingRequest, Registration
from app.models.taxonomy import Sector, Tag, TagCategory
from app.models.user import User

__all__ = [
    "Assignment",
    "AttendanceStatus",
    "Base",
    "Company",
    "Event",
    "EventStatus",
    "IdMixin",
    "Layout",
    "LayoutArea",
    "LayoutMode",
    "MatchReason",
    "MeetingRequest",
    "JobStatus",
    "MeetingRequestStatus",
    "Plan",
    "PlanStatus",
    "Profile",
    "ProfileTag",
    "Registration",
    "RegistrationStatus",
    "Sector",
    "Table",
    "TableKind",
    "Tag",
    "TagCategory",
    "TagDirection",
    "TimestampMixin",
    "User",
]
