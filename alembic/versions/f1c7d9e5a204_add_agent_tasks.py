"""add LangGraph agent tasks and training plan snapshots

Revision ID: f1c7d9e5a204
Revises: d6a1b8c4e203
Create Date: 2026-09-01

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1c7d9e5a204"
down_revision: Union[str, None] = "d6a1b8c4e203"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "ai_agent_task" not in inspector.get_table_names():
        op.create_table(
            "ai_agent_task",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("agent_code", sa.String(length=32), nullable=False),
            sa.Column("result_id", sa.Integer(), nullable=True),
            sa.Column("input_json", sa.JSON(), nullable=True),
            sa.Column("output_json", sa.JSON(), nullable=True),
            sa.Column("state_json", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("current_node", sa.String(length=64), nullable=True),
            sa.Column("retry_count", sa.Integer(), nullable=False),
            sa.Column("error_msg", sa.String(length=1000), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["result_id"], ["asm_result.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_ai_agent_task_agent_code"), "ai_agent_task", ["agent_code"], unique=False)
        op.create_index(op.f("ix_ai_agent_task_result_id"), "ai_agent_task", ["result_id"], unique=False)
        op.create_index(op.f("ix_ai_agent_task_status"), "ai_agent_task", ["status"], unique=False)
        op.create_index(op.f("ix_ai_agent_task_created_at"), "ai_agent_task", ["created_at"], unique=False)

    inspector = sa.inspect(op.get_bind())
    outbox_columns = {column["name"] for column in inspector.get_columns("asm_training_outbox")}
    outbox_indexes = {index["name"] for index in inspector.get_indexes("asm_training_outbox")}
    outbox_foreign_keys = {
        tuple(foreign_key["constrained_columns"])
        for foreign_key in inspector.get_foreign_keys("asm_training_outbox")
    }
    with op.batch_alter_table("asm_training_outbox") as batch_op:
        if "agent_task_id" not in outbox_columns:
            batch_op.add_column(sa.Column("agent_task_id", sa.Integer(), nullable=True))
        if "training_plan_json" not in outbox_columns:
            batch_op.add_column(sa.Column("training_plan_json", sa.JSON(), nullable=True))
        if op.f("ix_asm_training_outbox_agent_task_id") not in outbox_indexes:
            batch_op.create_index(op.f("ix_asm_training_outbox_agent_task_id"), ["agent_task_id"], unique=False)
        if ("agent_task_id",) not in outbox_foreign_keys:
            batch_op.create_foreign_key(
                "fk_asm_training_outbox_agent_task_id",
                "ai_agent_task",
                ["agent_task_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    with op.batch_alter_table("asm_training_outbox") as batch_op:
        batch_op.drop_constraint("fk_asm_training_outbox_agent_task_id", type_="foreignkey")
        batch_op.drop_index(op.f("ix_asm_training_outbox_agent_task_id"))
        batch_op.drop_column("training_plan_json")
        batch_op.drop_column("agent_task_id")

    op.drop_index(op.f("ix_ai_agent_task_created_at"), table_name="ai_agent_task")
    op.drop_index(op.f("ix_ai_agent_task_status"), table_name="ai_agent_task")
    op.drop_index(op.f("ix_ai_agent_task_result_id"), table_name="ai_agent_task")
    op.drop_index(op.f("ix_ai_agent_task_agent_code"), table_name="ai_agent_task")
    op.drop_table("ai_agent_task")
