"""add capability models for assessment auto papers

Revision ID: c4f8e2a19b70
Revises: b7e4c2d9a601
Create Date: 2026-09-01

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4f8e2a19b70"
down_revision: Union[str, None] = "b7e4c2d9a601"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "asm_capability_model" not in inspector.get_table_names():
        op.create_table(
            "asm_capability_model",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("description", sa.String(length=1000), nullable=False),
            sa.Column("position_id", sa.Integer(), nullable=True),
            sa.Column("position_level", sa.Integer(), nullable=True),
            sa.Column("rules", sa.JSON(), nullable=True),
            sa.Column("status", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["position_id"], ["sys_position.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name"),
        )
        op.create_index(op.f("ix_asm_capability_model_position_id"), "asm_capability_model", ["position_id"], unique=False)
        op.create_index(op.f("ix_asm_capability_model_position_level"), "asm_capability_model", ["position_level"], unique=False)
        op.create_index(op.f("ix_asm_capability_model_status"), "asm_capability_model", ["status"], unique=False)

    inspector = sa.inspect(op.get_bind())
    paper_columns = {column["name"] for column in inspector.get_columns("asm_paper")}
    paper_indexes = {index["name"] for index in inspector.get_indexes("asm_paper")}
    paper_foreign_keys = {
        tuple(foreign_key["constrained_columns"])
        for foreign_key in inspector.get_foreign_keys("asm_paper")
    }
    with op.batch_alter_table("asm_paper") as batch_op:
        if "generation_mode" not in paper_columns:
            batch_op.add_column(sa.Column("generation_mode", sa.String(length=16), nullable=False, server_default="manual"))
        if "capability_model_id" not in paper_columns:
            batch_op.add_column(sa.Column("capability_model_id", sa.Integer(), nullable=True))
        if "generation_rule" not in paper_columns:
            batch_op.add_column(sa.Column("generation_rule", sa.JSON(), nullable=True))
        if op.f("ix_asm_paper_capability_model_id") not in paper_indexes:
            batch_op.create_index(op.f("ix_asm_paper_capability_model_id"), ["capability_model_id"], unique=False)
        if ("capability_model_id",) not in paper_foreign_keys:
            batch_op.create_foreign_key(
                "fk_asm_paper_capability_model_id",
                "asm_capability_model",
                ["capability_model_id"],
                ["id"],
                ondelete="RESTRICT",
            )


def downgrade() -> None:
    with op.batch_alter_table("asm_paper") as batch_op:
        batch_op.drop_constraint("fk_asm_paper_capability_model_id", type_="foreignkey")
        batch_op.drop_index(op.f("ix_asm_paper_capability_model_id"))
        batch_op.drop_column("generation_rule")
        batch_op.drop_column("capability_model_id")
        batch_op.drop_column("generation_mode")

    op.drop_index(op.f("ix_asm_capability_model_status"), table_name="asm_capability_model")
    op.drop_index(op.f("ix_asm_capability_model_position_level"), table_name="asm_capability_model")
    op.drop_index(op.f("ix_asm_capability_model_position_id"), table_name="asm_capability_model")
    op.drop_table("asm_capability_model")
