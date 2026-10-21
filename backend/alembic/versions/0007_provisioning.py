"""provisioning per owner (REACH AI BOX register contract)

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-12

- owners                     業主: company / contact data
- sites                      owner, profile, contract and licence fields (site_profile)
- provisioning_tokens        per-owner factory tokens (hash only), quota, expiry, revocation
- edge_devices               mac_address (unique), admin_state, owner, provisioning token, registration times
- edge_device_audit          registered / re_registered / key_rotated / rejected_*
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
NOW = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "owners",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("company_name", sa.String(length=128), nullable=True),
        sa.Column("company_address", sa.String(length=256), nullable=True),
        sa.Column("company_phone", sa.String(length=32), nullable=True),
        sa.Column("tax_id", sa.String(length=8), nullable=True),
        sa.Column("contact_name", sa.String(length=128), nullable=True),
        sa.Column("contact_phone", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_owners")),
        sa.UniqueConstraint("name", name=op.f("uq_owners_name")),
    )

    op.add_column("sites", sa.Column("owner_id", sa.Uuid(), nullable=True))
    op.add_column("sites", sa.Column("profile", sa.String(length=16), nullable=True))
    op.add_column("sites", sa.Column("license_code", sa.String(length=128), nullable=True))
    op.add_column("sites", sa.Column("license_until", sa.Date(), nullable=True))
    op.add_column("sites", sa.Column("contract_no", sa.String(length=128), nullable=True))
    op.add_column("sites", sa.Column("term_years", sa.Integer(), nullable=True))
    op.add_column("sites", sa.Column("transaction_type", sa.String(length=16), nullable=True))
    op.create_foreign_key(op.f("fk_sites_owner_id_owners"), "sites", "owners", ["owner_id"], ["id"], ondelete="SET NULL")
    op.create_index(op.f("ix_sites_owner_id"), "sites", ["owner_id"])

    op.create_table(
        "provisioning_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("token_prefix", sa.String(length=16), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=True),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("site_id", sa.Uuid(), nullable=True),
        sa.Column("device_prefix", sa.String(length=16), nullable=False),
        sa.Column("max_devices", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"], name=op.f("fk_provisioning_tokens_owner_id_owners"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], name=op.f("fk_provisioning_tokens_site_id_sites"),
                                ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_provisioning_tokens_created_by_users"),
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_provisioning_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_provisioning_tokens_token_hash")),
    )
    op.create_index(op.f("ix_provisioning_tokens_owner_id"), "provisioning_tokens", ["owner_id"])

    op.add_column("edge_devices", sa.Column("mac_address", sa.String(length=17), nullable=True))
    op.add_column("edge_devices", sa.Column("admin_state", sa.String(length=16), server_default="active",
                                            nullable=False))
    op.add_column("edge_devices", sa.Column("owner_id", sa.Uuid(), nullable=True))
    op.add_column("edge_devices", sa.Column("provisioning_token_id", sa.Uuid(), nullable=True))
    op.add_column("edge_devices", sa.Column("registered_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("edge_devices", sa.Column("last_registered_at", sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint(op.f("uq_edge_devices_mac_address"), "edge_devices", ["mac_address"])
    op.create_foreign_key(op.f("fk_edge_devices_owner_id_owners"), "edge_devices", "owners", ["owner_id"], ["id"],
                          ondelete="SET NULL")
    op.create_foreign_key(op.f("fk_edge_devices_provisioning_token_id_provisioning_tokens"), "edge_devices",
                          "provisioning_tokens", ["provisioning_token_id"], ["id"], ondelete="SET NULL")
    op.create_index(op.f("ix_edge_devices_owner_id"), "edge_devices", ["owner_id"])

    op.create_table(
        "edge_device_audit",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("edge_device_id", sa.Uuid(), nullable=True),
        sa.Column("device_uuid", sa.String(length=64), nullable=True),
        sa.Column("mac_address", sa.String(length=17), nullable=True),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("source_ip", sa.String(length=64), nullable=True),
        sa.Column("token_prefix", sa.String(length=16), nullable=True),
        sa.Column("detail", JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.ForeignKeyConstraint(["edge_device_id"], ["edge_devices.id"],
                                name=op.f("fk_edge_device_audit_edge_device_id_edge_devices"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_edge_device_audit")),
    )
    op.create_index(op.f("ix_edge_device_audit_edge_device_id"), "edge_device_audit", ["edge_device_id"])
    op.create_index(op.f("ix_edge_device_audit_action"), "edge_device_audit", ["action"])
    op.create_index(op.f("ix_edge_device_audit_created_at"), "edge_device_audit", ["created_at"])


def downgrade() -> None:
    op.drop_table("edge_device_audit")
    op.drop_constraint(op.f("fk_edge_devices_provisioning_token_id_provisioning_tokens"), "edge_devices",
                       type_="foreignkey")
    op.drop_constraint(op.f("fk_edge_devices_owner_id_owners"), "edge_devices", type_="foreignkey")
    op.drop_constraint(op.f("uq_edge_devices_mac_address"), "edge_devices", type_="unique")
    op.drop_index(op.f("ix_edge_devices_owner_id"), table_name="edge_devices")
    for col in ("last_registered_at", "registered_at", "provisioning_token_id", "owner_id", "admin_state",
                "mac_address"):
        op.drop_column("edge_devices", col)
    op.drop_table("provisioning_tokens")
    op.drop_constraint(op.f("fk_sites_owner_id_owners"), "sites", type_="foreignkey")
    op.drop_index(op.f("ix_sites_owner_id"), table_name="sites")
    for col in ("transaction_type", "term_years", "contract_no", "license_until", "license_code", "profile",
                "owner_id"):
        op.drop_column("sites", col)
    op.drop_table("owners")
