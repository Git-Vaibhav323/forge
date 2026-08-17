"""create catalog_lines table for CSV brand evaluation

Revision ID: 009
Revises: 008
Create Date: 2026-08-18

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "catalog_lines",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("project_id", sa.String(length=32), nullable=False),
        sa.Column("document_id", sa.String(length=32), nullable=False),
        sa.Column("row_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("mfg_part_num", sa.String(length=128), nullable=False),
        sa.Column("part_desc", sa.Text(), nullable=False, server_default=""),
        sa.Column("e1_brand", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("unilog_brand", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("dib_brand", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("part_manuf", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("e1_brand_norm", sa.String(length=255), nullable=True),
        sa.Column("unilog_brand_norm", sa.String(length=255), nullable=True),
        sa.Column("dib_brand_norm", sa.String(length=255), nullable=True),
        sa.Column("part_manuf_norm", sa.String(length=255), nullable=True),
        sa.Column(
            "evaluation_status", sa.String(length=32), nullable=False, server_default="brand_gap"
        ),
        sa.Column("recommended_brand", sa.String(length=255), nullable=True),
        sa.Column("brand_source", sa.String(length=32), nullable=True),
        sa.Column("findings_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "document_id", "row_index", name="uq_catalog_project_doc_row"
        ),
    )
    op.create_index("ix_catalog_lines_project_id", "catalog_lines", ["project_id"])
    op.create_index("ix_catalog_lines_document_id", "catalog_lines", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_catalog_lines_document_id", table_name="catalog_lines")
    op.drop_index("ix_catalog_lines_project_id", table_name="catalog_lines")
    op.drop_table("catalog_lines")
