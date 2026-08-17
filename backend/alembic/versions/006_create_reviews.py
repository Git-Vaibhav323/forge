"""create review_items + review_decisions tables (M5 — review-service)

Revision ID: 006
Revises: 005
Create Date: 2026-08-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Per-source value on each evidence row, so a conflict can be rendered as
    # "datasheet says X / catalog says Y" instead of just two quotes.
    op.add_column("attribute_evidence", sa.Column("value", sa.String(length=255), nullable=True))
    op.add_column("attribute_evidence", sa.Column("unit", sa.String(length=32), nullable=True))

    op.create_table(
        "review_items",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("project_id", sa.String(length=32), nullable=False),
        sa.Column("field", sa.String(length=128), nullable=False),
        sa.Column("product_id", sa.String(length=64), nullable=True),
        sa.Column("issue_type", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="medium"),
        sa.Column("current_value", sa.Text(), nullable=True),
        sa.Column("proposed_value", sa.Text(), nullable=True),
        sa.Column("values_json", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("evidence_ids_json", sa.Text(), nullable=True),
        sa.Column("affected_products", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("signature", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("resolved_value", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        # Identity is (project_id, field) so items survive an evidence re-scan.
        sa.UniqueConstraint("project_id", "field", name="uq_review_items_project_field"),
    )
    op.create_index("ix_review_items_project_id", "review_items", ["project_id"])

    op.create_table(
        "review_decisions",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("review_item_id", sa.String(length=40), nullable=False),
        sa.Column("project_id", sa.String(length=32), nullable=False),
        sa.Column("field", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("propagate", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("affected_fields", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["review_item_id"], ["review_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_review_decisions_review_item_id", "review_decisions", ["review_item_id"]
    )
    op.create_index("ix_review_decisions_project_id", "review_decisions", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_review_decisions_project_id", table_name="review_decisions")
    op.drop_index("ix_review_decisions_review_item_id", table_name="review_decisions")
    op.drop_table("review_decisions")
    op.drop_index("ix_review_items_project_id", table_name="review_items")
    op.drop_table("review_items")
    op.drop_column("attribute_evidence", "unit")
    op.drop_column("attribute_evidence", "value")
