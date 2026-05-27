"""change_vector_dimension_to_768

Revision ID: a493c587575d
Revises: 554be4728801
Create Date: 2026-05-23 23:12:12.919465

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
# pyrefly: ignore [missing-import]
import pgvector.sqlalchemy  # <-- Ini kunci agar Python mengenali 'pgvector'

# revision identifiers, used by Alembic.
revision: str = 'a493c587575d'
down_revision: Union[str, Sequence[str], None] = '554be4728801'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Mengubah 1536 menjadi 768
    op.alter_column('product_catalog', 'embedding',
               existing_type=pgvector.sqlalchemy.vector.VECTOR(dim=1536),
               type_=pgvector.sqlalchemy.vector.VECTOR(dim=768),
               existing_nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    # Mengembalikan 768 menjadi 1536 jika di-rollback
    op.alter_column('product_catalog', 'embedding',
               existing_type=pgvector.sqlalchemy.vector.VECTOR(dim=768),
               type_=pgvector.sqlalchemy.vector.VECTOR(dim=1536),
               existing_nullable=True)