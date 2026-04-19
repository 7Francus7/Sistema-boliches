"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-19

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "venues",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("timezone", sa.String(64), server_default="America/Argentina/Buenos_Aires"),
        sa.Column("capacity_max", sa.Integer(), server_default="500"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("venue_id", UUID(as_uuid=True), sa.ForeignKey("venues.id", ondelete="CASCADE")),
        sa.Column("email", sa.String(180), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("pin_code", sa.String(10)),
        sa.Column("active", sa.Boolean(), server_default=sa.true()),
    )

    op.create_table(
        "devices",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("venue_id", UUID(as_uuid=True), sa.ForeignKey("venues.id", ondelete="CASCADE")),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("last_sync_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("venue_id", UUID(as_uuid=True), sa.ForeignKey("venues.id", ondelete="CASCADE")),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("capacity_override", sa.Integer()),
        sa.Column("status", sa.String(20), server_default="draft"),
    )

    op.create_table(
        "ticket_types",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", UUID(as_uuid=True), sa.ForeignKey("events.id", ondelete="CASCADE")),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("quota", sa.Integer(), server_default="0"),
        sa.Column("color_tag", sa.String(20), server_default="#fbbf24"),
    )

    op.create_table(
        "tickets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", UUID(as_uuid=True), sa.ForeignKey("events.id", ondelete="CASCADE")),
        sa.Column("ticket_type_id", UUID(as_uuid=True), sa.ForeignKey("ticket_types.id")),
        sa.Column("qr_code", sa.String(512), unique=True, nullable=False),
        sa.Column("buyer_name", sa.String(160)),
        sa.Column("buyer_doc", sa.String(40)),
        sa.Column("status", sa.String(20), server_default="valid"),
        sa.Column("sold_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("used_by_device_id", UUID(as_uuid=True), sa.ForeignKey("devices.id")),
        sa.Column("used_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id")),
    )
    op.create_index("ix_tickets_qr_code", "tickets", ["qr_code"])

    op.create_table(
        "access_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("client_uuid", UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_id", UUID(as_uuid=True), sa.ForeignKey("tickets.id", ondelete="CASCADE")),
        sa.Column("event_id", UUID(as_uuid=True), sa.ForeignKey("events.id", ondelete="CASCADE")),
        sa.Column("device_id", UUID(as_uuid=True), sa.ForeignKey("devices.id")),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("client_uuid", name="uq_access_logs_client_uuid"),
    )
    op.create_index("ix_access_logs_client_uuid", "access_logs", ["client_uuid"])

    op.create_table(
        "products",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("venue_id", UUID(as_uuid=True), sa.ForeignKey("venues.id", ondelete="CASCADE")),
        sa.Column("sku", sa.String(40), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("category", sa.String(60), server_default="barra"),
        sa.Column("cost_price", sa.Numeric(12, 2), server_default="0"),
        sa.Column("sale_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("unit", sa.String(20), server_default="u"),
        sa.Column("active", sa.Boolean(), server_default=sa.true()),
        sa.UniqueConstraint("venue_id", "sku", name="uq_products_venue_sku"),
    )

    op.create_table(
        "stock_levels",
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("venue_id", UUID(as_uuid=True), sa.ForeignKey("venues.id", ondelete="CASCADE")),
        sa.Column("qty_on_hand", sa.Integer(), server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "sales",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("client_uuid", UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", UUID(as_uuid=True), sa.ForeignKey("events.id", ondelete="CASCADE")),
        sa.Column("device_id", UUID(as_uuid=True), sa.ForeignKey("devices.id")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_method", sa.String(20), server_default="cash"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("client_uuid", name="uq_sales_client_uuid"),
    )
    op.create_index("ix_sales_client_uuid", "sales", ["client_uuid"])

    op.create_table(
        "sale_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("sale_id", UUID(as_uuid=True), sa.ForeignKey("sales.id", ondelete="CASCADE")),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id")),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("discount", sa.Numeric(12, 2), server_default="0"),
    )

    op.create_table(
        "stock_movements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("client_uuid", UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE")),
        sa.Column("event_id", UUID(as_uuid=True), sa.ForeignKey("events.id")),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("qty_delta", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("ref_sale_id", UUID(as_uuid=True), sa.ForeignKey("sales.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("client_uuid", name="uq_stock_movements_client_uuid"),
    )
    op.create_index("ix_stock_movements_client_uuid", "stock_movements", ["client_uuid"])


def downgrade() -> None:
    for t in [
        "stock_movements",
        "sale_items",
        "sales",
        "stock_levels",
        "products",
        "access_logs",
        "tickets",
        "ticket_types",
        "events",
        "devices",
        "users",
        "venues",
    ]:
        op.drop_table(t)
