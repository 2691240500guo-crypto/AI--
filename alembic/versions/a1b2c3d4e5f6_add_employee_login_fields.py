"""add employee login fields to sys_user (emp_no / talent_id / user_type)

Revision ID: a1b2c3d4e5f6
Revises: e8a3f0c1b2d4
Create Date: 2026-09-02

员工小程序登录优化（docs/01-需求分析.md 表结构改动）：
    - emp_no      员工工号（唯一索引，小程序工号登录）
    - talent_id   关联人才档案 tal_talent.id（本人数据隔离锚点）
    - user_type   admin / employee（登录入口分流：管理端 vs 小程序）
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
    columns = {c["name"] for c in inspector.get_columns("sys_user")}
    with op.batch_alter_table("sys_user") as batch_op:
        if "emp_no" not in columns:
            batch_op.add_column(sa.Column("emp_no", sa.String(length=32), nullable=True))
        if "talent_id" not in columns:
            batch_op.add_column(sa.Column("talent_id", sa.Integer(), nullable=True))
        if "user_type" not in columns:
            batch_op.add_column(sa.Column("user_type", sa.String(length=16), nullable=False, server_default="admin"))
    # 唯一索引（工号）
    index_names = {ix["name"] for ix in sa.inspect(bind).get_indexes("sys_user")}
    if "ix_sys_user_emp_no" not in index_names:
        op.create_index(op.f("ix_sys_user_emp_no"), "sys_user", ["emp_no"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_sys_user_emp_no"), table_name="sys_user")
    with op.batch_alter_table("sys_user") as batch_op:
        batch_op.drop_column("user_type")
        batch_op.drop_column("talent_id")
        batch_op.drop_column("emp_no")
