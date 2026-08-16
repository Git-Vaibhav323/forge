"""create attributes + attribute_evidence tables

Revision ID: 004
Revises: 003
Create Date: 2026-08-16

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "attributes",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("project_id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("raw_value", sa.Text(), nullable=False, server_default=""),
        sa.Column("normalized_value", sa.String(length=255), nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="missing"),
        sa.Column("risk_level", sa.String(length=16), nullable=False, server_default="low"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_attributes_project_id", "attributes", ["project_id"])

    op.create_table(
        "attribute_evidence",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("attribute_id", sa.String(length=40), nullable=False),
        sa.Column("document_id", sa.String(length=32), nullable=False),
        sa.Column("document_name", sa.String(length=512), nullable=False),
        sa.Column("document_type", sa.String(length=64), nullable=True),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["attribute_id"], ["attributes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_attribute_evidence_attribute_id", "attribute_evidence", ["attribute_id"])


def downgrade() -> None:
    op.drop_index("ix_attribute_evidence_attribute_id", table_name="attribute_evidence")
    op.drop_table("attribute_evidence")
    op.drop_index("ix_attributes_project_id", table_name="attributes")
    op.drop_table("attributes")
