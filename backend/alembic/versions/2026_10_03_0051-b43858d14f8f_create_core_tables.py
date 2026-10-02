"""create core tables

Revision ID: b43858d14f8f
Revises:
Create Date: 2026-10-03 00:51:47.407600

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b43858d14f8f"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Enum columns are VARCHAR(20) + a named CHECK constraint (see app.models.enums).
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column(
            "role",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('admin', 'business', 'driver')", name=op.f("ck_users_user_role")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_index(op.f("ix_users_role"), "users", ["role"], unique=False)
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_audit_logs_actor_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index(op.f("ix_audit_logs_actor_id"), "audit_logs", ["actor_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_created_at"), "audit_logs", ["created_at"], unique=False)
    op.create_index(
        "ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"], unique=False
    )
    op.create_table(
        "businesses",
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "category",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=False),
        sa.Column("lat", sa.Double(), nullable=False),
        sa.Column("lng", sa.Double(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "category IN ('restaurant', 'pharmacy', 'grocery', 'retail', 'other')",
            name=op.f("ck_businesses_business_category"),
        ),
        sa.CheckConstraint(
            "lat BETWEEN -90 AND 90 AND lng BETWEEN -180 AND 180",
            name=op.f("ck_businesses_valid_coordinates"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_businesses_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_businesses")),
        sa.UniqueConstraint("owner_id", name=op.f("uq_businesses_owner_id")),
    )
    op.create_table(
        "drivers",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column(
            "vehicle_type",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="offline",
            nullable=False,
        ),
        sa.Column("current_lat", sa.Double(), nullable=True),
        sa.Column("current_lng", sa.Double(), nullable=True),
        sa.Column("location_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('available', 'busy', 'offline')", name=op.f("ck_drivers_driver_status")
        ),
        sa.CheckConstraint(
            "vehicle_type IN ('motorbike', 'car', 'bicycle')", name=op.f("ck_drivers_vehicle_type")
        ),
        sa.CheckConstraint(
            "(current_lat IS NULL) = (current_lng IS NULL)",
            name=op.f("ck_drivers_location_both_or_neither"),
        ),
        sa.CheckConstraint(
            "current_lat IS NULL OR (current_lat BETWEEN -90 AND 90 AND current_lng BETWEEN -180 AND 180)",
            name=op.f("ck_drivers_valid_coordinates"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_drivers_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_drivers")),
        sa.UniqueConstraint("user_id", name=op.f("uq_drivers_user_id")),
    )
    op.create_index(op.f("ix_drivers_status"), "drivers", ["status"], unique=False)
    op.create_table(
        "orders",
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("driver_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("customer_name", sa.String(length=120), nullable=False),
        sa.Column("customer_phone", sa.String(length=20), nullable=False),
        sa.Column("pickup_address", sa.String(length=255), nullable=False),
        sa.Column("pickup_lat", sa.Double(), nullable=False),
        sa.Column("pickup_lng", sa.Double(), nullable=False),
        sa.Column("dropoff_address", sa.String(length=255), nullable=False),
        sa.Column("dropoff_lat", sa.Double(), nullable=False),
        sa.Column("dropoff_lng", sa.Double(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("deliver_by", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_overdue", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("assignment_attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("picked_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.String(length=255), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(status = 'pending' AND driver_id IS NULL) OR status = 'failed' OR (status IN ('assigned', 'picked_up', 'delivered') AND driver_id IS NOT NULL)",
            name=op.f("ck_orders_driver_matches_status"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'assigned', 'picked_up', 'delivered', 'failed')",
            name=op.f("ck_orders_order_status"),
        ),
        sa.CheckConstraint(
            "status NOT IN ('picked_up', 'delivered') OR accepted_at IS NOT NULL",
            name=op.f("ck_orders_accepted_before_pickup"),
        ),
        sa.CheckConstraint(
            "dropoff_lat BETWEEN -90 AND 90 AND dropoff_lng BETWEEN -180 AND 180",
            name=op.f("ck_orders_valid_dropoff"),
        ),
        sa.CheckConstraint(
            "pickup_lat BETWEEN -90 AND 90 AND pickup_lng BETWEEN -180 AND 180",
            name=op.f("ck_orders_valid_pickup"),
        ),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name=op.f("fk_orders_business_id_businesses"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["driver_id"],
            ["drivers.id"],
            name=op.f("fk_orders_driver_id_drivers"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orders")),
    )
    op.create_index(op.f("ix_orders_business_id"), "orders", ["business_id"], unique=False)
    op.create_index(op.f("ix_orders_driver_id"), "orders", ["driver_id"], unique=False)
    op.create_index("ix_orders_status_created_at", "orders", ["status", "created_at"], unique=False)
    op.create_index(
        "uq_orders_driver_active",
        "orders",
        ["driver_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('assigned', 'picked_up')"),
    )
    op.create_table(
        "order_assignments",
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("driver_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="offered",
            nullable=False,
        ),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "status IN ('offered', 'accepted', 'expired', 'completed', 'failed')",
            name=op.f("ck_order_assignments_assignment_status"),
        ),
        sa.ForeignKeyConstraint(
            ["driver_id"],
            ["drivers.id"],
            name=op.f("fk_order_assignments_driver_id_drivers"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_assignments_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_assignments")),
    )
    op.create_index(
        op.f("ix_order_assignments_driver_id"), "order_assignments", ["driver_id"], unique=False
    )
    op.create_index(
        op.f("ix_order_assignments_order_id"), "order_assignments", ["order_id"], unique=False
    )
    op.create_index(
        "uq_order_assignments_order_open",
        "order_assignments",
        ["order_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('offered', 'accepted')"),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(
        "uq_order_assignments_order_open",
        table_name="order_assignments",
        postgresql_where=sa.text("status IN ('offered', 'accepted')"),
    )
    op.drop_index(op.f("ix_order_assignments_order_id"), table_name="order_assignments")
    op.drop_index(op.f("ix_order_assignments_driver_id"), table_name="order_assignments")
    op.drop_table("order_assignments")
    op.drop_index(
        "uq_orders_driver_active",
        table_name="orders",
        postgresql_where=sa.text("status IN ('assigned', 'picked_up')"),
    )
    op.drop_index("ix_orders_status_created_at", table_name="orders")
    op.drop_index(op.f("ix_orders_driver_id"), table_name="orders")
    op.drop_index(op.f("ix_orders_business_id"), table_name="orders")
    op.drop_table("orders")
    op.drop_index(op.f("ix_drivers_status"), table_name="drivers")
    op.drop_table("drivers")
    op.drop_table("businesses")
    op.drop_index("ix_audit_logs_entity", table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_created_at"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_actor_id"), table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index(op.f("ix_users_role"), table_name="users")
    op.drop_table("users")
    # ### end Alembic commands ###
