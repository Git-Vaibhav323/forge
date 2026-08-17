"""create relationship, compatibility and BOM tables (M6 — relationship-service)

Revision ID: 007
Revises: 006
Create Date: 2026-08-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "product_relationships",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("project_id", sa.String(length=32), nullable=False),
        sa.Column("related_project_id", sa.String(length=32), nullable=False),
        sa.Column("relation", sa.String(length=32), nullable=False, server_default="variant"),
        sa.Column("basis", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "related_project_id", "relation", name="uq_relationship_pair"
        ),
    )
    op.create_index(
        "ix_product_relationships_project_id", "product_relationships", ["project_id"]
    )
    op.create_index(
        "ix_product_relationships_related_project_id",
        "product_relationships",
        ["related_project_id"],
    )

    op.create_table(
        "compatibility_findings",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("project_id", sa.String(length=32), nullable=False),
        sa.Column("rule", sa.String(length=64), nullable=False),
        sa.Column("field", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="unknown"),
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="medium"),
        sa.Column("required_value", sa.String(length=255), nullable=True),
        sa.Column("rated_value", sa.String(length=255), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("evidence_ids_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "rule", name="uq_compat_project_rule"),
    )
    op.create_index(
        "ix_compatibility_findings_project_id", "compatibility_findings", ["project_id"]
    )

    op.create_table(
        "bom_lines",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("project_id", sa.String(length=32), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="specification"),
        sa.Column("component", sa.String(length=512), nullable=False),
        sa.Column("quantity", sa.String(length=32), nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="missing"),
        sa.Column("source_field", sa.String(length=128), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("evidence_ids_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "position", name="uq_bom_project_position"),
    )
    op.create_index("ix_bom_lines_project_id", "bom_lines", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_bom_lines_project_id", table_name="bom_lines")
    op.drop_table("bom_lines")
    op.drop_index("ix_compatibility_findings_project_id", table_name="compatibility_findings")
    op.drop_table("compatibility_findings")
    op.drop_index(
        "ix_product_relationships_related_project_id", table_name="product_relationships"
    )
    op.drop_index("ix_product_relationships_project_id", table_name="product_relationships")
    op.drop_table("product_relationships")
