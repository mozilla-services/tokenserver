# flake8: noqa
"""add_keys_changed_at_column

Revision ID: 75e8ca84b0bc
Revises: 2b968b28bcdc
Create Date: 2019-10-14 12:09:18.257878

"""

# revision identifiers, used by Alembic.
revision = '75e8ca84b0bc'
down_revision = '2b968b28bcdc'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # Create the column, making it nullable so that it can be
    # safely inserted in the present of existing data.
    op.add_column(
        'users',
        sa.Column('keys_changed_at', sa.BigInteger(), nullable=True)
    )
    pass


def downgrade():
    op.drop_column('users', 'keys_changed_at')
