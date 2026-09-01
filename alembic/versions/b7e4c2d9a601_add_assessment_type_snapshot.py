"""add question type snapshot to assessment paper questions

Revision ID: b7e4c2d9a601
Revises: 9f2c0b4a7d11
Create Date: 2026-08-31

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7e4c2d9a601"
down_revision: Union[str, None] = "9f2c0b4a7d11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("asm_paper_question")}
    if "type_snapshot" in columns:
        return
    op.add_column(
        "asm_paper_question",
        sa.Column("type_snapshot", sa.String(length=16), nullable=False, server_default="single"),
    )
    op.execute(
        "UPDATE asm_paper_question "
        "SET type_snapshot = (SELECT type FROM asm_question "
        "WHERE asm_question.id = asm_paper_question.question_id)"
    )


def downgrade() -> None:
    op.drop_column("asm_paper_question", "type_snapshot")
