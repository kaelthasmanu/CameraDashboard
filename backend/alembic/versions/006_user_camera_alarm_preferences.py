"""Add per-user camera alarm preferences."""

from alembic import op
import sqlalchemy as sa


revision = "006_user_camera_alarm_preferences"
down_revision = "005_user_activity_and_presence"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_camera_alarm_preferences",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("camera_name", sa.String(length=120), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "camera_name"),
        if_not_exists=True,
    )


def downgrade():
    op.drop_table("user_camera_alarm_preferences")
