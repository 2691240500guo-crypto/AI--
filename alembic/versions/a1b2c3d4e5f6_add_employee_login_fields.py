"""add employee identity fields to sys_user.

Revision ID: a1b2c3d4e5f6
Revises: e8a3f0c1b2d4
Create Date: 2026-09-02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "e8a3f0c1b2d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("sys_user")}
    with op.batch_alter_table("sys_user") as batch_op:
        if "talent_id" not in columns:
            batch_op.add_column(sa.Column("talent_id", sa.Integer(), nullable=True))
        if "user_type" not in columns:
            batch_op.add_column(
                sa.Column("user_type", sa.String(length=16), nullable=False, server_default="admin")
            )

    index_names = {index["name"] for index in sa.inspect(bind).get_indexes("sys_user")}
    if "ix_sys_user_talent_id" not in index_names:
        op.create_index(op.f("ix_sys_user_talent_id"), "sys_user", ["talent_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_sys_user_talent_id"), table_name="sys_user")
    with op.batch_alter_table("sys_user") as batch_op:
        batch_op.drop_column("user_type")
        batch_op.drop_column("talent_id")
