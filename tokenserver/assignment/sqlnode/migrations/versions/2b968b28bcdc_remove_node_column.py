# flake8: noqa
"""remove node column

Revision ID: 2b968b28bcdc
Revises: 9fb109457bd
Create Date: 2014-06-27 09:41:22.944863

"""

# revision identifiers, used by Alembic.
revision = '2b968b28bcdc'
down_revision = '9fb109457bd'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.drop_column('users', 'node')


def downgrade():
    # Re-create the column, making it nullable so that it
    # can be safely inserted in the presence of existing data.
    # The previous migration knows how to make it non-nullable.
    op.add_column(
        'users',
        sa.Column('node', sa.String(64), nullable=True)
    )
