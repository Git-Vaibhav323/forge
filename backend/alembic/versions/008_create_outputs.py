"""create outputs table (M8 — generation-service)

Revision ID: 008
Revises: 007
Create Date: 2026-08-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "outputs",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("project_id", sa.String(length=32), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
        sa.Column("storage_key", sa.String(length=1024), nullable=True),
        sa.Column(
            "content_type", sa.String(length=128), nullable=False, server_default="text/markdown"
        ),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("qa_notes_json", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        # Regenerating an output replaces it rather than piling up copies.
        sa.UniqueConstraint("project_id", "type", name="uq_outputs_project_type"),
    )
    op.create_index("ix_outputs_project_id", "outputs", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_outputs_project_id", table_name="outputs")
    op.drop_table("outputs")
