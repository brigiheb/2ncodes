"""Add prix_achat and moyenne to DureeAvecStock

Revision ID: d843015a7a68
Revises: 131d9cf66924
Create Date: 2025-06-09 10:26:51.096170

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd843015a7a68'
down_revision = '131d9cf66924'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('duree_avec_stock', schema=None) as batch_op:
        batch_op.add_column(sa.Column('prix_achat', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('moyenne', sa.Float(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('duree_avec_stock', schema=None) as batch_op:
        batch_op.drop_column('moyenne')
        batch_op.drop_column('prix_achat')

    # ### end Alembic commands ###
