"""add assessment batches and result batch links

Revision ID: d6a1b8c4e203
Revises: c4f8e2a19b70
Create Date: 2026-09-01

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d6a1b8c4e203"
down_revision: Union[str, None] = "c4f8e2a19b70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "asm_assessment_batch" not in inspector.get_table_names():
        op.create_table(
            "asm_assessment_batch",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("batch_no", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("paper_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.Integer(), nullable=False),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("deadline_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["created_by"], ["sys_user.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["paper_id"], ["asm_paper.id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("batch_no"),
        )
        op.create_index(op.f("ix_asm_assessment_batch_batch_no"), "asm_assessment_batch", ["batch_no"], unique=False)
        op.create_index(op.f("ix_asm_assessment_batch_paper_id"), "asm_assessment_batch", ["paper_id"], unique=False)
        op.create_index(op.f("ix_asm_assessment_batch_status"), "asm_assessment_batch", ["status"], unique=False)
        op.create_index(op.f("ix_asm_assessment_batch_created_by"), "asm_assessment_batch", ["created_by"], unique=False)
        op.create_index(op.f("ix_asm_assessment_batch_created_at"), "asm_assessment_batch", ["created_at"], unique=False)

    inspector = sa.inspect(op.get_bind())
    result_columns = {column["name"] for column in inspector.get_columns("asm_result")}
    result_indexes = {index["name"] for index in inspector.get_indexes("asm_result")}
    result_foreign_keys = {
        tuple(foreign_key["constrained_columns"])
        for foreign_key in inspector.get_foreign_keys("asm_result")
    }
    with op.batch_alter_table("asm_result") as batch_op:
        if "batch_id" not in result_columns:
            batch_op.add_column(sa.Column("batch_id", sa.Integer(), nullable=True))
        if op.f("ix_asm_result_batch_id") not in result_indexes:
            batch_op.create_index(op.f("ix_asm_result_batch_id"), ["batch_id"], unique=False)
        if "ix_asm_result_batch_status" not in result_indexes:
            batch_op.create_index("ix_asm_result_batch_status", ["batch_id", "status"], unique=False)
        if ("batch_id",) not in result_foreign_keys:
            batch_op.create_foreign_key(
                "fk_asm_result_batch_id",
                "asm_assessment_batch",
                ["batch_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    with op.batch_alter_table("asm_result") as batch_op:
        batch_op.drop_constraint("fk_asm_result_batch_id", type_="foreignkey")
        batch_op.drop_index("ix_asm_result_batch_status")
        batch_op.drop_index(op.f("ix_asm_result_batch_id"))
        batch_op.drop_column("batch_id")

    op.drop_index(op.f("ix_asm_assessment_batch_created_at"), table_name="asm_assessment_batch")
    op.drop_index(op.f("ix_asm_assessment_batch_created_by"), table_name="asm_assessment_batch")
    op.drop_index(op.f("ix_asm_assessment_batch_status"), table_name="asm_assessment_batch")
    op.drop_index(op.f("ix_asm_assessment_batch_paper_id"), table_name="asm_assessment_batch")
    op.drop_index(op.f("ix_asm_assessment_batch_batch_no"), table_name="asm_assessment_batch")
    op.drop_table("asm_assessment_batch")
