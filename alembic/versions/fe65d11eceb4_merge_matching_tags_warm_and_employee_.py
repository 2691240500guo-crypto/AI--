"""merge matching tags/warm and employee login heads

Revision ID: fe65d11eceb4
Revises: 72d0f4a9c3e6, a1b2c3d4e5f6
Create Date: 2026-09-02 13:38:05.664115

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fe65d11eceb4'
down_revision: Union[str, None] = ('72d0f4a9c3e6', 'a1b2c3d4e5f6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
