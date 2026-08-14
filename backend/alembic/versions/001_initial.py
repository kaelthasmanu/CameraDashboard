from alembic import op
import sqlalchemy as sa

revision = "001_initial"; down_revision = None; branch_labels = None; depends_on = None
def upgrade():
    op.create_table("cameras", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(120), nullable=False), sa.Column("location", sa.String(180), nullable=False), sa.Column("model", sa.String(120), nullable=False), sa.Column("stream_url", sa.String(500), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("enabled", sa.Boolean(), nullable=False), sa.Column("last_seen", sa.DateTime(timezone=True)))
    op.create_table("recordings", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("camera_id", sa.Integer(), sa.ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False), sa.Column("filename", sa.String(255), nullable=False), sa.Column("path", sa.String(1000), nullable=False, unique=True), sa.Column("start_time", sa.DateTime(timezone=True), nullable=False), sa.Column("end_time", sa.DateTime(timezone=True), nullable=False), sa.Column("size_bytes", sa.Integer(), nullable=False), sa.Column("duration_seconds", sa.Integer(), nullable=False))
    op.create_index("ix_recordings_camera_id", "recordings", ["camera_id"]); op.create_index("ix_recordings_start_time", "recordings", ["start_time"])
def downgrade():
    op.drop_table("recordings"); op.drop_table("cameras")
