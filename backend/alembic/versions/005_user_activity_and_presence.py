"""Add persistent dashboard activity and browser-presence state.

Revision ID: 005_user_activity_and_presence
Revises: 004_user_camera_access
"""

from alembic import op
import sqlalchemy as sa


revision = "005_user_activity_and_presence"
down_revision = "004_user_camera_access"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_activity_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("camera_name", sa.String(length=120), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_activity_events_user_id", "user_activity_events", ["user_id"])
    op.create_index("ix_user_activity_events_event_type", "user_activity_events", ["event_type"])
    op.create_index("ix_user_activity_events_camera_name", "user_activity_events", ["camera_name"])
    op.create_index("ix_user_activity_events_occurred_at", "user_activity_events", ["occurred_at"])

    op.create_table(
        "user_presence_sessions",
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_visible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index("ix_user_presence_sessions_user_id", "user_presence_sessions", ["user_id"])
    op.create_index("ix_user_presence_sessions_last_seen_at", "user_presence_sessions", ["last_seen_at"])


def downgrade():
    op.drop_index("ix_user_presence_sessions_last_seen_at", table_name="user_presence_sessions")
    op.drop_index("ix_user_presence_sessions_user_id", table_name="user_presence_sessions")
    op.drop_table("user_presence_sessions")

    op.drop_index("ix_user_activity_events_occurred_at", table_name="user_activity_events")
    op.drop_index("ix_user_activity_events_camera_name", table_name="user_activity_events")
    op.drop_index("ix_user_activity_events_event_type", table_name="user_activity_events")
    op.drop_index("ix_user_activity_events_user_id", table_name="user_activity_events")
    op.drop_table("user_activity_events")
