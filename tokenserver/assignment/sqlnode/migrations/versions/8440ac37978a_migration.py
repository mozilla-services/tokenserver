"""migration

Revision ID: 8440ac37978a
Revises: 75e8ca84b0bc
Create Date: 2019-12-16 15:46:07.048437

"""

# revision identifiers, used by Alembic.
revision = '8440ac37978a'
down_revision = '75e8ca84b0bc'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column("users", sa.Column("migration_state", sa.String))
    pass


def downgrade():
    op.drop_column("users", "migration_state")
    pass
