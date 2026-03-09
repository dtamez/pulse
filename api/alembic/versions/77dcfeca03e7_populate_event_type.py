"""populate event type

Revision ID: 77dcfeca03e7
Revises: c99aa2071c21
Create Date: 2026-03-06 21:00:06.686781

"""

import uuid
from typing import Sequence, Union

from alembic import op

from core.models import EventType

# revision identifiers, used by Alembic.
revision: str = "77dcfeca03e7"
down_revision: Union[str, Sequence[str], None] = "c99aa2071c21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.bulk_insert(
        EventType.__table__,
        [
            {"id": uuid.uuid4(), "name": "api_call", "description": "API Call"},
            {"id": uuid.uuid4(), "name": "page_view", "description": "Page View"},
            {"id": uuid.uuid4(), "name": "job_started", "description": "Job Started"},
            {
                "id": uuid.uuid4(),
                "name": "job_completed",
                "description": "Job Completed",
            },
            {"id": uuid.uuid4(), "name": "job_failed", "description": "Job Failed"},
            {"id": uuid.uuid4(), "name": "purchase", "description": "Purchase"},
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("""
               DELETE FROM event_type;
               """)
