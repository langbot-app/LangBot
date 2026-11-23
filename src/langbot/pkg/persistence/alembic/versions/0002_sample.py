"""example: sample migration demonstrating Alembic patterns

This is a SAMPLE showing how to write migrations that work
seamlessly across SQLite and PostgreSQL. Delete or adapt as needed.

Revision ID: 0002_sample
Revises: 0001_baseline
Create Date: 2026-04-08

Patterns demonstrated:
  1. Schema change (add column) — works on both DBs via render_as_batch
  2. Data migration (read + modify JSON) — pure SQLAlchemy, no dialect branching
"""

revision = '0002_sample'
down_revision = '0001_baseline'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    EXAMPLE: Uncomment to use. This shows the patterns.

    # --- Pattern 1: Schema change (add/drop column) ---
    # render_as_batch=True in env.py makes this work on SQLite too.
    #
    # op.add_column('pipelines', sa.Column('description', sa.String(512), server_default=''))

    # --- Pattern 2: Data migration (read + modify JSON field) ---
    # No if/else for sqlite vs postgres needed!
    #
    # conn = op.get_bind()
    # rows = conn.execute(sa.text("SELECT uuid, config FROM pipelines")).fetchall()
    # for row in rows:
    #     config = json.loads(row[1]) if isinstance(row[1], str) else row[1]
    #     # Modify the config
    #     config.setdefault('ai', {}).setdefault('some_new_key', 'default_value')
    #     conn.execute(
    #         sa.text("UPDATE pipelines SET config = :cfg WHERE uuid = :uuid"),
    #         {"cfg": json.dumps(config), "uuid": row[0]}
    #     )

    # --- Pattern 3: Create a new table ---
    #
    # op.create_table(
    #     'audit_log',
    #     sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
    #     sa.Column('action', sa.String(255), nullable=False),
    #     sa.Column('detail', sa.Text),
    #     sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    # )
    """
    pass


def downgrade() -> None:
    """
    # op.drop_column('pipelines', 'description')
    # op.drop_table('audit_log')
    """
    pass
