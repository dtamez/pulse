"""populate event type

Revision ID: 77dcfeca03e7
Revises: c99aa2071c21
Create Date: 2026-03-06 21:00:06.686781

"""

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
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "name": "api_call",
                "description": "API Call",
            },
            {
                "id": "22222222-2222-2222-2222-222222222222",
                "name": "page_view",
                "description": "Page View",
            },
            {
                "id": "33333333-3333-3333-3333-333333333333",
                "name": "job_started",
                "description": "Job Started",
            },
            {
                "id": "44444444-4444-4444-4444-444444444444",
                "name": "job_completed",
                "description": "Job Completed",
            },
            {
                "id": "55555555-5555-5555-5555-555555555555",
                "name": "job_failed",
                "description": "Job Failed",
            },
            {
                "id": "66666666-6666-6666-6666-666666666666",
                "name": "purchase",
                "description": "Purchase",
            },
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("""
               DELETE FROM event_type;
               """)
