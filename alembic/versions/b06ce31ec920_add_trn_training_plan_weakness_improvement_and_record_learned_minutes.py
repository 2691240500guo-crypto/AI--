"""add trn_training_plan.weakness_tags/improvement and trn_learning_record.learned_minutes

课件硬需求：
- trn_training_plan.weakness_tags    能力短板/缺口  (课件①能力缺口智能诊断)
- trn_training_plan.improvement      提升幅度      (课件④成长轨迹可视化)
- trn_learning_record.learned_minutes实际学习时长 (课件③学习全流程管控)

Revision ID: b06ce31ec920
Revises: 513968600ebc
Create Date: 2026-09-01 09:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b06ce31ec920'
down_revision: Union[str, None] = '513968600ebc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    table_columns = {
        table: {column["name"] for column in inspector.get_columns(table)}
        for table in ("trn_training_plan", "trn_learning_record")
        if table in inspector.get_table_names()
    }
    if "trn_training_plan" in table_columns:
        if "weakness_tags" not in table_columns["trn_training_plan"]:
            op.add_column(
                "trn_training_plan",
                sa.Column("weakness_tags", sa.String(length=500), nullable=False, server_default=""),
            )
        if "improvement" not in table_columns["trn_training_plan"]:
            op.add_column(
                "trn_training_plan",
                sa.Column("improvement", sa.Integer(), nullable=False, server_default="0"),
            )
    if "trn_learning_record" in table_columns and "learned_minutes" not in table_columns["trn_learning_record"]:
        op.add_column(
            "trn_learning_record",
            sa.Column("learned_minutes", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    table_columns = {
        table: {column["name"] for column in inspector.get_columns(table)}
        for table in ("trn_training_plan", "trn_learning_record")
        if table in inspector.get_table_names()
    }
    if "learned_minutes" in table_columns.get("trn_learning_record", set()):
        op.drop_column("trn_learning_record", "learned_minutes")
    if "improvement" in table_columns.get("trn_training_plan", set()):
        op.drop_column("trn_training_plan", "improvement")
    if "weakness_tags" in table_columns.get("trn_training_plan", set()):
        op.drop_column("trn_training_plan", "weakness_tags")
