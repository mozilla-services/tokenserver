"""create dyn_settings table

Revision ID: 5d056c5b8f57
Revises: 75e8ca84b0bc
Create Date: 2020-01-06 08:16:15.546054

"""

# revision identifiers, used by Alembic.
revision = '5d056c5b8f57'
down_revision = '75e8ca84b0bc'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        'dynamic_settings',
        sa.Column('setting', sa.String(100), primary_key=True),
        sa.Column('value', sa.String(255), nullable=False),
        sa.Column('description', sa.String(255))
    )


def downgrade():
    op.drop_table('dynamic_settings')
    pass
