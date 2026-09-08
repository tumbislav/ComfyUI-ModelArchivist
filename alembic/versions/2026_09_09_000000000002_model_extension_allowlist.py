# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: 2026_09_09_000000000002_model_extension_allowlist.py
# purpose: Persist the global model-extension allowlist without changing existing scans
# ---------------------------------------------------------------------------

from alembic import op
import sqlalchemy as sa

revision = '000000000002'
down_revision = '000000000001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('applicationsettings', sa.Column('model_extension_allowlist', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('applicationsettings') as batch:
        batch.drop_column('model_extension_allowlist')
