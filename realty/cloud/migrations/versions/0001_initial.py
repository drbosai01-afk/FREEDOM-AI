"""Initial schema, versioned and non-destructive. Includes email challenges and audit table.

Revision ID: 0001_initial
Revises:
"""
from alembic import op
from sqlalchemy import inspect
from main import Base

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    connection = op.get_bind()
    # Baseline for an EMPTY database. Refuse migration of unknown existing databases.
    existing = set(inspect(connection).get_table_names())
    expected = set(Base.metadata.tables)
    if (existing - {"alembic_version"}) & expected:
        raise RuntimeError("Existing tables found: use a reviewed database baseline migration")
    for name in ('users', 'records', 'email_challenges', 'auth_attempts',
                 'snapshots', 'snapshot_chunks', 'cloud_states', 'cloud_state_history'):
        Base.metadata.tables[name].create(bind=connection, checkfirst=False)

def downgrade():
    raise RuntimeError("Destructive schema rollback is deliberately disabled: restore a DB backup instead")
