"""restore the deployed merge marker for employee/matching/lesson heads

Revision ID: d4e5f6a7b8c9
Revises: a7b3c4d5e6f7, fe65d11eceb4
Create Date: 2026-09-02

This no-op merge revision already exists in the shared database's
``alembic_version`` table but its source file was not committed. Restoring the
marker reconnects the deployed database to repository history without
manually rewriting its version stamp.
"""

from typing import Sequence, Union


revision: str = "d4e5f6a7b8c9"
down_revision: Union[tuple[str, str], None] = ("a7b3c4d5e6f7", "fe65d11eceb4")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
