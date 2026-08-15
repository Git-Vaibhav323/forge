"""create questions table

Revision ID: 003
Revises: 002
Create Date: 2026-08-16

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "questions",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("project_id", sa.String(length=32), nullable=False),
        sa.Column("field", sa.String(length=128), nullable=False),
        sa.Column("text", sa.String(length=512), nullable=False),
        sa.Column("input_type", sa.String(length=32), nullable=False),
        sa.Column("options_json", sa.Text(), nullable=True),
        sa.Column("why_asked", sa.String(length=1024), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_questions_project_id", "questions", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_questions_project_id", table_name="questions")
    op.drop_table("questions")
