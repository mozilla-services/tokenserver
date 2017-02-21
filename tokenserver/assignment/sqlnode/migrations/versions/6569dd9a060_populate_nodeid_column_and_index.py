# flake8: noqa
"""populate nodeid column and index

Revision ID: 6569dd9a060
Revises: 846f28d1b6f
Create Date: 2014-04-14 05:26:44.146236

This updates the values in  the "nodeid" column to ensure that they match
the value in the string-based "node" column, then indexes the column for fast
node-based lookup.  It should only be applied *after* all servers have bee
upgraded to properly write the value of the "nodeid" column; it's part 2 of 2
in getting to the desired state without downtime.

See https://bugzilla.mozilla.org/show_bug.cgi?id=988643

"""

# revision identifiers, used by Alembic.
revision = '6569dd9a060'
down_revision = '846f28d1b6f'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # Populate nodeid with the proper id for each existing row.
    # XXX NOTE: MySQL-specific!
    op.execute("""
        UPDATE users, nodes
        SET users.nodeid = nodes.id
        WHERE users.node = nodes.node
    """.strip())
    # Set the column non-nullable so it doesn't mask bugs in the future.
    op.alter_column(
        'users', 'nodeid',
        nullable=False,
        existing_type=sa.BigInteger(),
        existing_server_default=None,
    )
    # Index the nodeid column.
    op.create_index('node_idx', 'users', ['nodeid'])


def downgrade():
    op.drop_index('node_idx', 'users')
    op.alter_column(
        'users', 'nodeid',
        nullable=True,
        existing_type=sa.BigInteger(),
        existing_server_default=None,
    )
