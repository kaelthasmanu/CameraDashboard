from alembic import op
import sqlalchemy as sa


revision = "004_user_camera_access"
down_revision = "003_user_roles"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_camera_access",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("camera_name", sa.String(length=120), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "camera_name"),
    )


def downgrade():
    op.drop_table("user_camera_access")
