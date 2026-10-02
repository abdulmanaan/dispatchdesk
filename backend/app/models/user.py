"""User accounts. Every person logging in is a user with exactly one role."""

from typing import TYPE_CHECKING

from sqlalchemy import String, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import UserRole, enum_column
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.business import Business
    from app.models.driver import Driver


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    # Stored lower-cased by the application, so a plain unique index is enough.
    email: Mapped[str] = mapped_column(String(255), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[UserRole] = mapped_column(enum_column(UserRole, "user_role"), index=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())

    business: Mapped["Business | None"] = relationship(back_populates="owner")
    driver: Mapped["Driver | None"] = relationship(back_populates="user")
