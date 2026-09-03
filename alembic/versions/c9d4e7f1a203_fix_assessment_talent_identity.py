"""separate assessment talent identity from login account identity

Revision ID: c9d4e7f1a203
Revises: a7b3c4d5e6f7, fe65d11eceb4
Create Date: 2026-09-03

The original assessment schema stored ``sys_user.id`` in ``asm_result.talent_id``.
This migration preserves that value as ``user_id`` and resolves the real talent
through ``sys_user.talent_id`` before changing the foreign key.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c9d4e7f1a203"
down_revision: Union[tuple[str, str], None] = ("a7b3c4d5e6f7", "fe65d11eceb4")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector: sa.Inspector, table: str) -> bool:
    return table in inspector.get_table_names()


def _foreign_key_name(inspector: sa.Inspector, table: str, column: str) -> str | None:
    for foreign_key in inspector.get_foreign_keys(table):
        if foreign_key.get("constrained_columns") == [column]:
            return foreign_key.get("name")
    return None


def _unresolved_count(bind) -> int:
    # The old value is copied to user_id before talent_id is rewritten.
    query = sa.text(
        "SELECT COUNT(*) FROM asm_result r "
        "LEFT JOIN sys_user u ON u.id = r.user_id "
        "LEFT JOIN tal_talent t ON t.id = u.talent_id "
        "WHERE r.user_id IS NULL OR u.id IS NULL OR u.talent_id IS NULL OR t.id IS NULL"
    )
    return int(bind.execute(query).scalar() or 0)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    required = {"asm_result", "sys_user", "tal_talent"}
    missing = sorted(table for table in required if not _table_exists(inspector, table))
    if missing:
        raise RuntimeError(
            "assessment identity migration requires tables: " + ", ".join(missing)
        )

    result_columns = {column["name"] for column in inspector.get_columns("asm_result")}
    if "user_id" not in result_columns:
        op.add_column("asm_result", sa.Column("user_id", sa.Integer(), nullable=True))
        inspector = sa.inspect(bind)

    # Old rows use sys_user.id in talent_id. Keep that value and resolve the
    # actual talent through the explicit sys_user.talent_id relationship.
    bind.execute(sa.text(
        "UPDATE asm_result SET user_id = talent_id WHERE user_id IS NULL"
    ))
    bind.execute(sa.text(
        "UPDATE asm_result SET talent_id = ("
        "SELECT u.talent_id FROM sys_user u WHERE u.id = asm_result.user_id"
        ") WHERE user_id IS NOT NULL"
    ))

    unresolved = _unresolved_count(bind)
    if unresolved:
        raise RuntimeError(
            f"无法迁移 {unresolved} 条 asm_result：请先为对应 sys_user 设置有效 talent_id"
        )

    dialect = bind.dialect.name
    old_talent_fk = _foreign_key_name(inspector, "asm_result", "talent_id")
    user_fk = _foreign_key_name(inspector, "asm_result", "user_id")

    if dialect == "sqlite":
        # SQLite cannot alter/drop foreign keys in place. Batch recreation also
        # preserves all unrelated indexes and constraints on asm_result.
        with op.batch_alter_table("asm_result", recreate="always") as batch_op:
            if old_talent_fk:
                batch_op.drop_constraint(old_talent_fk, type_="foreignkey")
            if user_fk:
                batch_op.drop_constraint(user_fk, type_="foreignkey")
            batch_op.alter_column("talent_id", existing_type=sa.Integer(), nullable=False)
            batch_op.alter_column("user_id", existing_type=sa.Integer(), nullable=False)
            batch_op.create_foreign_key(
                "fk_asm_result_talent_id_tal_talent",
                "tal_talent",
                ["talent_id"],
                ["id"],
                ondelete="RESTRICT",
            )
            batch_op.create_foreign_key(
                "fk_asm_result_user_id_sys_user",
                "sys_user",
                ["user_id"],
                ["id"],
                ondelete="RESTRICT",
            )
    else:
        if old_talent_fk:
            op.drop_constraint(old_talent_fk, "asm_result", type_="foreignkey")
        if user_fk:
            op.drop_constraint(user_fk, "asm_result", type_="foreignkey")
        op.alter_column("asm_result", "talent_id", existing_type=sa.Integer(), nullable=False)
        op.alter_column("asm_result", "user_id", existing_type=sa.Integer(), nullable=False)
        op.create_foreign_key(
            "fk_asm_result_talent_id_tal_talent",
            "asm_result",
            "talent_id",
            "tal_talent",
            ["id"],
            ondelete="RESTRICT",
        )
        op.create_foreign_key(
            "fk_asm_result_user_id_sys_user",
            "asm_result",
            "user_id",
            "sys_user",
            ["id"],
            ondelete="RESTRICT",
        )

    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("asm_result")}
    if "ix_asm_result_user_id" not in indexes:
        op.create_index("ix_asm_result_user_id", "asm_result", ["user_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "asm_result"):
        return
    columns = {column["name"] for column in inspector.get_columns("asm_result")}
    if "user_id" not in columns:
        return

    # Restore the old schema only when every row has a corresponding account.
    unresolved = int(bind.execute(sa.text(
        "SELECT COUNT(*) FROM asm_result r "
        "LEFT JOIN sys_user u ON u.id = r.user_id "
        "WHERE r.user_id IS NULL OR u.id IS NULL"
    )).scalar() or 0)
    if unresolved:
        raise RuntimeError(f"无法回滚 {unresolved} 条 asm_result：缺少原登录账号")

    bind.execute(sa.text("UPDATE asm_result SET talent_id = user_id"))
    inspector = sa.inspect(bind)
    talent_fk = _foreign_key_name(inspector, "asm_result", "talent_id")
    user_fk = _foreign_key_name(inspector, "asm_result", "user_id")
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("asm_result", recreate="always") as batch_op:
            if talent_fk:
                batch_op.drop_constraint(talent_fk, type_="foreignkey")
            if user_fk:
                batch_op.drop_constraint(user_fk, type_="foreignkey")
            batch_op.alter_column("talent_id", existing_type=sa.Integer(), nullable=False)
            batch_op.drop_column("user_id")
            batch_op.create_foreign_key(
                "fk_asm_result_talent_id_sys_user",
                "sys_user",
                ["talent_id"],
                ["id"],
                ondelete="RESTRICT",
            )
    else:
        if talent_fk:
            op.drop_constraint(talent_fk, "asm_result", type_="foreignkey")
        if user_fk:
            op.drop_constraint(user_fk, "asm_result", type_="foreignkey")
        op.drop_index("ix_asm_result_user_id", table_name="asm_result")
        op.drop_column("asm_result", "user_id")
        op.create_foreign_key(
            "fk_asm_result_talent_id_sys_user",
            "asm_result",
            "talent_id",
            "sys_user",
            ["id"],
            ondelete="RESTRICT",
        )
