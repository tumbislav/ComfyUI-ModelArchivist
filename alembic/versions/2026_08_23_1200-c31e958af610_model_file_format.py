# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: 2026_08_23_1200-c31e958af610_model_file_format.py
# purpose: Add the model weights file format
# ---------------------------------------------------------------------------

"""add model file format

Revision ID: c31e958af610
Revises: a7c4f02d91e8
"""

from pathlib import Path

from alembic import op
import sqlalchemy as sa


revision = 'c31e958af610'
down_revision = 'a7c4f02d91e8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('model') as batch_op:
        batch_op.add_column(sa.Column(
            'file_format', sa.String(), nullable=False, server_default=''))

    connection = op.get_bind()
    components = connection.execute(sa.text(
        """SELECT componentset.model_id, component.file_name
           FROM component
           JOIN componentset ON component.component_set_id = componentset.id
           WHERE component.component_type = 'model'
             AND componentset.model_id IS NOT NULL"""
    )).fetchall()
    formats: dict[str, str] = {}
    for model_id, file_name in components:
        suffix = Path(file_name).suffix.lower().removeprefix('.')
        if suffix:
            formats.setdefault(model_id, suffix)
    for model_id, file_format in formats.items():
        connection.execute(
            sa.text("UPDATE model SET file_format = :file_format WHERE id = :model_id"),
            {'file_format': file_format, 'model_id': model_id},
        )


def downgrade() -> None:
    with op.batch_alter_table('model') as batch_op:
        batch_op.drop_column('file_format')
