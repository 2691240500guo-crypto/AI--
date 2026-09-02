"""add matching tags persistence and talent warm(/保温) management fields

需求补齐：
- pos_position.parsed_json    岗位智能解析结果落库持久化（tags/技能/学历/经验/综合素质），支持重查与追溯（需求1）
- match_result.warm_level     储备人才保温等级（0无 1低 2中 3高），支撑保温管理（需求4）
- match_result.last_follow_up 最近一次跟进时间（需求4）

Revision ID: 72d0f4a9c3e6
Revises: e8a3f0c1b2d4
Create Date: 2026-09-02 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '72d0f4a9c3e6'
down_revision: Union[str, None] = 'e8a3f0c1b2d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'pos_position',
        sa.Column('parsed_json', sa.Text(), nullable=True,
                  comment='岗位智能解析结果 JSON（tags/skill_standards/学历经验等）'),
    )
    op.add_column(
        'match_result',
        sa.Column('warm_level', sa.Integer(), nullable=False, server_default='0',
                  comment='储备人才保温等级：0无 1低 2中 3高'),
    )
    op.add_column(
        'match_result',
        sa.Column('last_follow_up', sa.DateTime(), nullable=True,
                  comment='最近一次跟进时间（保温管理）'),
    )


def downgrade() -> None:
    op.drop_column('match_result', 'last_follow_up')
    op.drop_column('match_result', 'warm_level')
    op.drop_column('pos_position', 'parsed_json')