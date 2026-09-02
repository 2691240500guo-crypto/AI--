"""add trn_lesson.video_id

Revision ID: a7b3c4d5e6f7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-02 18:25:00
"""
from alembic import op
import sqlalchemy as sa

revision = "a7b3c4d5e6f7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("trn_lesson", sa.Column("video_id", sa.Integer(), nullable=True))
    op.create_index("idx_lesson_video", "trn_lesson", ["video_id"])


def downgrade() -> None:
    op.drop_index("idx_lesson_video", table_name="trn_lesson")
    op.drop_column("trn_lesson", "video_id")
