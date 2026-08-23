# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: 2026_08_22_1900-a7c4f02d91e8_component_file_stats.py
# purpose: Add filesystem snapshot fields to components
# ---------------------------------------------------------------------------

"""add component filesystem statistics

Revision ID: a7c4f02d91e8
Revises: 16da8f3ac79c
"""

from alembic import op
import sqlalchemy as sa


revision = 'a7c4f02d91e8'
down_revision = '16da8f3ac79c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('component') as batch_op:
        batch_op.add_column(sa.Column('size', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('modified_at_ns', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    with op.batch_alter_table('component') as batch_op:
        batch_op.drop_column('modified_at_ns')
        batch_op.drop_column('size')
