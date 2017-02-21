# flake8: noqa
"""add nodeid column

Revision ID: 846f28d1b6f
Revises: 3d5af3924466
Create Date: 2014-04-14 03:28:16.156769

This adds a new "nodeid" column to the users table, for referencing a row
in the "nodes" table.  It doesn't make the column *useful* to the app since
it needs to be properly populated from the existing data, which we can't do
until the app is updated to write into it.  It's part 1 of 2 in getting to
the desired state without downtime.

See https://bugzilla.mozilla.org/show_bug.cgi?id=988643

"""

# revision identifiers, used by Alembic.
revision = '846f28d1b6f'
down_revision = '3d5af3924466'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # Create the column, making it nullable so that it can be
    # safely inserted in the present of existing data.
    # The next migration will make it non-nullable.
    op.add_column(
        'users',
        sa.Column('nodeid', sa.BigInteger(), nullable=True)
    )


def downgrade():
    op.drop_column('users', 'nodeid')
