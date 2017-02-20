# flake8: noqa
"""drop clientstate_idx

Revision ID: 3d5af3924466
Revises: 17d209a72e2f
Create Date: 2014-04-14 02:47:55.094158

This drops the "clientstate_idx" index from the users table.
It was a unique index, but we no longer require them to be unique
at this level.  See https://bugzilla.mozilla.org/show_bug.cgi?id=988134

"""

# revision identifiers, used by Alembic.
revision = '3d5af3924466'
down_revision = '17d209a72e2f'

from alembic import op


def upgrade():
    op.drop_index('clientstate_idx', 'users')


def downgrade():
    op.create_unique_constraint('clientstate_idx', 'users',
                                ['email', 'service', 'client_state'])
