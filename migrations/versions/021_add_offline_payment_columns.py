"""Add offline payment columns

Revision ID: 021_add_offline_payment_columns
Revises: 60f574e19344
Create Date: 2026-07-08 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '021_add_offline_payment_columns'
down_revision: Union[str, None] = '60f574e19344'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Add new offline payment columns to payment_transactions
    op.add_column('payment_transactions', sa.Column('reference_number', sa.String(length=255), nullable=True))
    op.add_column('payment_transactions', sa.Column('payment_date', sa.DateTime(timezone=True), nullable=True))
    op.add_column('payment_transactions', sa.Column('bank_name', sa.String(length=255), nullable=True))
    op.add_column('payment_transactions', sa.Column('branch_name', sa.String(length=255), nullable=True))
    op.add_column('payment_transactions', sa.Column('account_holder_name', sa.String(length=255), nullable=True))
    op.add_column('payment_transactions', sa.Column('cheque_image_url', sa.String(length=500), nullable=True))
    op.add_column('payment_transactions', sa.Column('remarks', sa.String(length=1000), nullable=True))

def downgrade() -> None:
    op.drop_column('payment_transactions', 'reference_number')
    op.drop_column('payment_transactions', 'payment_date')
    op.drop_column('payment_transactions', 'bank_name')
    op.drop_column('payment_transactions', 'branch_name')
    op.drop_column('payment_transactions', 'account_holder_name')
    op.drop_column('payment_transactions', 'cheque_image_url')
    op.drop_column('payment_transactions', 'remarks')
