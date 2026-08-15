from alembic import op
import sqlalchemy as sa

revision = "002_users"
down_revision = "001_initial"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(120), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

def downgrade():
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
