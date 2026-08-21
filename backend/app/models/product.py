import uuid

from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class Category(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Product(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "products"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("categories.id"), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)  # kg, bag, litre, etc.
    price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    minimum_order_quantity: Mapped[float] = mapped_column(Numeric(12, 2), default=1)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    procurement_cycle_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("procurement_cycles.id"), nullable=True
    )

    category: Mapped[Category] = relationship(back_populates="products")
    procurement_cycle: Mapped["ProcurementCycle | None"] = relationship()
