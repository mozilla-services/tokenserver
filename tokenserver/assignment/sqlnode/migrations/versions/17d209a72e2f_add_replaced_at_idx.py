# flake8: noqa
"""add replaced_at_idx

Revision ID: 17d209a72e2f
Revises: None
Create Date: 2014-04-14 02:42:04.919012

This adds an index on ("service", "replaced_at") to the users table.
See https://bugzilla.mozilla.org/show_bug.cgi?id=984232

"""

# revision identifiers, used by Alembic.
revision = '17d209a72e2f'
down_revision = None

from alembic import op


def upgrade():
    op.create_index('replaced_at_idx', 'users', ['service', 'replaced_at'])


def downgrade():
    op.drop_index('replaced_at_idx', 'users')
