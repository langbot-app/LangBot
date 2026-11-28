"""Persist one-time Harness TOTP handoffs."""

from alembic import op

from langbot.pkg.entity.persistence.harness_oauth import HarnessHandoff

revision = '0066_harness_handoff'
down_revision = '0065_harness_key_rotation'
branch_labels = None
depends_on = None


def upgrade():
    HarnessHandoff.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    HarnessHandoff.__table__.drop(op.get_bind(), checkfirst=True)
