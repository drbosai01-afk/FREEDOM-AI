"""Versioned read-only public/catalog seed entries.

Revision ID: 0002_catalog_entries
Revises: 0001_initial
"""
from alembic import op
from main import Base
revision = "0002_catalog_entries"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

def upgrade():
    Base.metadata.tables["catalog_entries"].create(bind=op.get_bind(), checkfirst=False)

def downgrade():
    raise RuntimeError("Catalog table cannot be dropped automatically")
