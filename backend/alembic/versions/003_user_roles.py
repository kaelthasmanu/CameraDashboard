from alembic import op
import sqlalchemy as sa


revision = "003_user_roles"
down_revision = "002_users"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=20), nullable=False, server_default="guardia"),
    )
    # Existing non-admin accounts previously had access to recordings. Keep
    # that access after the upgrade; newly created accounts choose explicitly.
    op.execute("UPDATE users SET role = CASE WHEN is_admin THEN 'admin' ELSE 'supervisor' END")


def downgrade():
    op.drop_column("users", "role")
