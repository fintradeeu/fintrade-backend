"""Allow referral registration before a student selects a course.

Revision ID: 017_referral_course_nullable
Revises: 016_ib_self_registration
Create Date: 2026-06-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "017_referral_course_nullable"
down_revision: Union[str, None] = "016_ib_self_registration"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("student_referrals"):
        return

    course_id = next(
        (column for column in inspector.get_columns("student_referrals") if column["name"] == "course_id"),
        None,
    )
    if course_id and not course_id["nullable"]:
        op.alter_column(
            "student_referrals",
            "course_id",
            existing_type=sa.Integer(),
            nullable=True,
        )


def downgrade() -> None:
    # Pre-enrollment referrals legitimately have no course. Reintroducing the
    # constraint could destroy valid data, so the downgrade is a safe no-op.
    pass
