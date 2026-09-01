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
    op.add_column(
        'trn_training_plan',
        sa.Column('weakness_tags', sa.String(length=500), nullable=False, server_default=''),
    )
    op.add_column(
        'trn_training_plan',
        sa.Column('improvement', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column(
        'trn_learning_record',
        sa.Column('learned_minutes', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_column('trn_learning_record', 'learned_minutes')
    op.drop_column('trn_training_plan', 'improvement')
    op.drop_column('trn_training_plan', 'weakness_tags')
