# flake8: noqa
"""make users.node column nullable

Revision ID: 9fb109457bd
Revises: 6569dd9a060
Create Date: 2014-04-29 12:51:41.879429

"""

# revision identifiers, used by Alembic.
revision = '9fb109457bd'
down_revision = '6569dd9a060'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.alter_column(
        'users', 'node',
        nullable=True,
        existing_type=sa.String(64),
        existing_server_default=None,
    )


def downgrade():
    # Populate the column with denormalized data from the nodes table.
    # XXX NOTE: MySQL-specific!
    op.execute("""
        UPDATE users, nodes
        SET users.node = nodes.node
        WHERE users.nodeid = nodes.id
    """.strip())
    op.alter_column(
        'users', 'node',
        nullable=False,
        existing_type=sa.String(64),
        existing_server_default=None,
    )
