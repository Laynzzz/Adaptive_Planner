"""Run the same migrations against the configured application or injected test DB."""

from alembic import context
from sqlalchemy import create_engine, pool

from planner.db import adaptation_models  # noqa: F401 - register adaptation metadata
from planner.db import ai_models  # noqa: F401 - register interpretation metadata
from planner.db import calendar_models  # noqa: F401 - register calendar metadata
from planner.db import job_models  # noqa: F401 - register dispatcher metadata
from planner.db import weekday_models  # noqa: F401 - register reviewed weekday rules
from planner.db.models import Base
from planner.settings import Settings

config = context.config
url = config.attributes.get("database_url") or Settings().database_url

if context.is_offline_mode():
    context.configure(url=url, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
