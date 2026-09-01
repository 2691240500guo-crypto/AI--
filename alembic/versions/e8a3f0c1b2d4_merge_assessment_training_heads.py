"""merge the remote training and local assessment migration heads"""

from typing import Sequence, Union


revision: str = "e8a3f0c1b2d4"
down_revision: Union[tuple[str, str], None] = (
    "b06ce31ec920",
    "f1c7d9e5a204",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
