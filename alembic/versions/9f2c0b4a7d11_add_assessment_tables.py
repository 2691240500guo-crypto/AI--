"""add C assessment tables

Revision ID: 9f2c0b4a7d11
Revises: 513968600ebc
Create Date: 2026-08-31

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9f2c0b4a7d11"
down_revision: Union[str, None] = "513968600ebc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    expected_tables = {
        "asm_question_bank",
        "asm_question",
        "asm_paper",
        "asm_paper_question",
        "asm_result",
        "asm_result_detail",
        "asm_answer_event",
        "asm_training_outbox",
    }
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
    present_tables = expected_tables & existing_tables
    if present_tables:
        missing_tables = expected_tables - existing_tables
        if missing_tables:
            raise RuntimeError(
                "C assessment schema is partially initialized; missing tables: "
                + ", ".join(sorted(missing_tables))
            )
        return

    op.create_table(
        "asm_question_bank",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=False),
        sa.Column("status", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_asm_question_bank_status"), "asm_question_bank", ["status"], unique=False)

    op.create_table(
        "asm_question",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("bank_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column("answer", sa.JSON(), nullable=True),
        sa.Column("dimension", sa.String(length=64), nullable=False),
        sa.Column("difficulty", sa.Integer(), nullable=False),
        sa.Column("score", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("status", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["bank_id"], ["asm_question_bank.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_asm_question_bank_id"), "asm_question", ["bank_id"], unique=False)
    op.create_index(op.f("ix_asm_question_dimension"), "asm_question", ["dimension"], unique=False)
    op.create_index(op.f("ix_asm_question_status"), "asm_question", ["status"], unique=False)
    op.create_index("ix_asm_question_bank_status_pair", "asm_question", ["bank_id", "status"], unique=False)

    op.create_table(
        "asm_paper",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=False),
        sa.Column("bank_ids", sa.JSON(), nullable=True),
        sa.Column("difficulty", sa.Integer(), nullable=True),
        sa.Column("total_score", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("duration", sa.Integer(), nullable=False),
        sa.Column("status", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_asm_paper_status"), "asm_paper", ["status"], unique=False)

    op.create_table(
        "asm_paper_question",
        sa.Column("paper_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("sort", sa.Integer(), nullable=False),
        sa.Column("content_snapshot", sa.Text(), nullable=False),
        sa.Column("options_snapshot", sa.JSON(), nullable=True),
        sa.Column("answer_snapshot", sa.JSON(), nullable=True),
        sa.Column("dimension_snapshot", sa.String(length=64), nullable=False),
        sa.Column("score_snapshot", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.ForeignKeyConstraint(["paper_id"], ["asm_paper.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["asm_question.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("paper_id", "question_id"),
        sa.UniqueConstraint("paper_id", "question_id", name="uq_asm_paper_question"),
    )

    op.create_table(
        "asm_result",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("talent_id", sa.Integer(), nullable=False),
        sa.Column("paper_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.Integer(), nullable=False),
        sa.Column("score", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("correct_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("deadline_at", sa.DateTime(), nullable=True),
        sa.Column("end_at", sa.DateTime(), nullable=True),
        sa.Column("answer_json", sa.JSON(), nullable=True),
        sa.Column("report_json", sa.JSON(), nullable=True),
        sa.Column("report_source", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["paper_id"], ["asm_paper.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["talent_id"], ["sys_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_asm_result_created_at"), "asm_result", ["created_at"], unique=False)
    op.create_index(op.f("ix_asm_result_deadline_at"), "asm_result", ["deadline_at"], unique=False)
    op.create_index(op.f("ix_asm_result_paper_id"), "asm_result", ["paper_id"], unique=False)
    op.create_index(op.f("ix_asm_result_status"), "asm_result", ["status"], unique=False)
    op.create_index(op.f("ix_asm_result_talent_id"), "asm_result", ["talent_id"], unique=False)
    op.create_index("ix_asm_result_paper_status", "asm_result", ["paper_id", "status"], unique=False)
    op.create_index("ix_asm_result_talent_status", "asm_result", ["talent_id", "status"], unique=False)

    op.create_table(
        "asm_result_detail",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("result_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("user_answer", sa.JSON(), nullable=True),
        sa.Column("is_correct", sa.Integer(), nullable=False),
        sa.Column("score", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["asm_question.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["result_id"], ["asm_result.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("result_id", "question_id", name="uq_asm_result_detail"),
    )
    op.create_index(op.f("ix_asm_result_detail_question_id"), "asm_result_detail", ["question_id"], unique=False)
    op.create_index(op.f("ix_asm_result_detail_result_id"), "asm_result_detail", ["result_id"], unique=False)

    op.create_table(
        "asm_answer_event",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("result_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("detail", sa.String(length=1000), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["result_id"], ["asm_result.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_asm_answer_event_created_at"), "asm_answer_event", ["created_at"], unique=False)
    op.create_index(op.f("ix_asm_answer_event_result_id"), "asm_answer_event", ["result_id"], unique=False)
    op.create_index("ix_asm_answer_event_result_type", "asm_answer_event", ["result_id", "event_type"], unique=False)

    op.create_table(
        "asm_training_outbox",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("result_id", sa.Integer(), nullable=False),
        sa.Column("weak_dimensions", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["result_id"], ["asm_result.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("result_id"),
    )
    op.create_index(op.f("ix_asm_training_outbox_created_at"), "asm_training_outbox", ["created_at"], unique=False)
    op.create_index(op.f("ix_asm_training_outbox_result_id"), "asm_training_outbox", ["result_id"], unique=False)
    op.create_index(op.f("ix_asm_training_outbox_status"), "asm_training_outbox", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_asm_training_outbox_status"), table_name="asm_training_outbox")
    op.drop_index(op.f("ix_asm_training_outbox_result_id"), table_name="asm_training_outbox")
    op.drop_index(op.f("ix_asm_training_outbox_created_at"), table_name="asm_training_outbox")
    op.drop_table("asm_training_outbox")

    op.drop_index("ix_asm_answer_event_result_type", table_name="asm_answer_event")
    op.drop_index(op.f("ix_asm_answer_event_result_id"), table_name="asm_answer_event")
    op.drop_index(op.f("ix_asm_answer_event_created_at"), table_name="asm_answer_event")
    op.drop_table("asm_answer_event")

    op.drop_index(op.f("ix_asm_result_detail_result_id"), table_name="asm_result_detail")
    op.drop_index(op.f("ix_asm_result_detail_question_id"), table_name="asm_result_detail")
    op.drop_table("asm_result_detail")

    op.drop_index("ix_asm_result_talent_status", table_name="asm_result")
    op.drop_index("ix_asm_result_paper_status", table_name="asm_result")
    op.drop_index(op.f("ix_asm_result_talent_id"), table_name="asm_result")
    op.drop_index(op.f("ix_asm_result_status"), table_name="asm_result")
    op.drop_index(op.f("ix_asm_result_paper_id"), table_name="asm_result")
    op.drop_index(op.f("ix_asm_result_deadline_at"), table_name="asm_result")
    op.drop_index(op.f("ix_asm_result_created_at"), table_name="asm_result")
    op.drop_table("asm_result")

    op.drop_table("asm_paper_question")

    op.drop_index(op.f("ix_asm_question_status"), table_name="asm_question")
    op.drop_index("ix_asm_question_bank_status_pair", table_name="asm_question")
    op.drop_index(op.f("ix_asm_question_dimension"), table_name="asm_question")
    op.drop_index(op.f("ix_asm_question_bank_id"), table_name="asm_question")
    op.drop_table("asm_question")

    op.drop_index(op.f("ix_asm_paper_status"), table_name="asm_paper")
    op.drop_table("asm_paper")
    op.drop_index(op.f("ix_asm_question_bank_status"), table_name="asm_question_bank")
    op.drop_table("asm_question_bank")
