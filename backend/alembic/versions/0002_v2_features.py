"""v2: turnos, RRPP, cashless, proveedores, recepciones, alertas

Revision ID: 0002_v2_features
Revises: 0001_initial
Create Date: 2026-04-19

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "0002_v2_features"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shifts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("venue_id", UUID(as_uuid=True), sa.ForeignKey("venues.id", ondelete="CASCADE")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("device_id", UUID(as_uuid=True), sa.ForeignKey("devices.id")),
        sa.Column("event_id", UUID(as_uuid=True), sa.ForeignKey("events.id")),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("opening_cash", sa.Numeric(12, 2), server_default="0"),
        sa.Column("closing_cash", sa.Numeric(12, 2)),
        sa.Column("expected_cash", sa.Numeric(12, 2)),
        sa.Column("cash_variance", sa.Numeric(12, 2)),
        sa.Column("notes", sa.Text()),
    )

    op.create_table(
        "promoters",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("venue_id", UUID(as_uuid=True), sa.ForeignKey("venues.id", ondelete="CASCADE")),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(60), nullable=False),
        sa.Column("phone", sa.String(40)),
        sa.Column("commission_pct", sa.Numeric(5, 2), server_default="10"),
        sa.Column("active", sa.Boolean(), server_default=sa.true()),
        sa.UniqueConstraint("venue_id", "slug", name="uq_promoters_venue_slug"),
    )

    op.add_column("tickets", sa.Column("promoter_id", UUID(as_uuid=True), sa.ForeignKey("promoters.id", ondelete="SET NULL"), nullable=True))

    op.create_table(
        "tabs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("venue_id", UUID(as_uuid=True), sa.ForeignKey("venues.id", ondelete="CASCADE")),
        sa.Column("event_id", UUID(as_uuid=True), sa.ForeignKey("events.id")),
        sa.Column("code", sa.String(60), nullable=False),
        sa.Column("holder_name", sa.String(120)),
        sa.Column("holder_doc", sa.String(40)),
        sa.Column("balance", sa.Numeric(12, 2), server_default="0"),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("venue_id", "code", name="uq_tabs_venue_code"),
    )

    op.create_table(
        "tab_movements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("client_uuid", UUID(as_uuid=True), nullable=False),
        sa.Column("tab_id", UUID(as_uuid=True), sa.ForeignKey("tabs.id", ondelete="CASCADE")),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("ref_sale_id", UUID(as_uuid=True), sa.ForeignKey("sales.id", ondelete="SET NULL")),
        sa.Column("device_id", UUID(as_uuid=True), sa.ForeignKey("devices.id")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("client_uuid", name="uq_tab_movements_client_uuid"),
    )
    op.create_index("ix_tab_movements_client_uuid", "tab_movements", ["client_uuid"])

    op.add_column("sales", sa.Column("tab_id", UUID(as_uuid=True), sa.ForeignKey("tabs.id", ondelete="SET NULL"), nullable=True))
    op.add_column("sales", sa.Column("shift_id", UUID(as_uuid=True), sa.ForeignKey("shifts.id", ondelete="SET NULL"), nullable=True))

    op.create_table(
        "suppliers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("venue_id", UUID(as_uuid=True), sa.ForeignKey("venues.id", ondelete="CASCADE")),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("contact", sa.String(120)),
        sa.Column("phone", sa.String(40)),
        sa.Column("email", sa.String(180)),
        sa.Column("tax_id", sa.String(40)),
        sa.Column("active", sa.Boolean(), server_default=sa.true()),
    )

    op.create_table(
        "purchases",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("venue_id", UUID(as_uuid=True), sa.ForeignKey("venues.id", ondelete="CASCADE")),
        sa.Column("supplier_id", UUID(as_uuid=True), sa.ForeignKey("suppliers.id")),
        sa.Column("reference", sa.String(80)),
        sa.Column("total", sa.Numeric(12, 2), server_default="0"),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id")),
    )

    op.create_table(
        "purchase_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("purchase_id", UUID(as_uuid=True), sa.ForeignKey("purchases.id", ondelete="CASCADE")),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id")),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("unit_cost", sa.Numeric(12, 2), nullable=False),
    )

    op.add_column("products", sa.Column("low_stock_threshold", sa.Integer(), server_default="10"))


def downgrade() -> None:
    op.drop_column("products", "low_stock_threshold")
    op.drop_table("purchase_items")
    op.drop_table("purchases")
    op.drop_table("suppliers")
    op.drop_column("sales", "shift_id")
    op.drop_column("sales", "tab_id")
    op.drop_index("ix_tab_movements_client_uuid", table_name="tab_movements")
    op.drop_table("tab_movements")
    op.drop_table("tabs")
    op.drop_column("tickets", "promoter_id")
    op.drop_table("promoters")
    op.drop_table("shifts")
