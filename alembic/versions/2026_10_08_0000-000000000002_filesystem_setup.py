# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: 2026_10_08_0000-000000000002_filesystem_setup.py
# purpose: Persist completion of one-time filesystem root setup
# ---------------------------------------------------------------------------

from alembic import op
import sqlalchemy as sa

revision = '000000000002'
down_revision = '000000000001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('applicationsettings') as batch:
        batch.add_column(sa.Column('filesystem_setup_complete', sa.Boolean(), nullable=False,
                                   server_default=sa.true()))
    with op.batch_alter_table('applicationsettings') as batch:
        batch.alter_column('filesystem_setup_complete', server_default=None)


def downgrade() -> None:
    with op.batch_alter_table('applicationsettings') as batch:
        batch.drop_column('filesystem_setup_complete')
