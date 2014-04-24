import os
import sys

# ensure that the containing module is on sys.path
# this is a hack for using alembic in our built virtualenv.
mod_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
if mod_dir not in sys.path:
    sys.path.append(mod_dir)

from alembic import context
from logging.config import fileConfig

from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from tokenserver.util import find_config_file
from mozsvc.config import load_into_settings

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)


ini_file = find_config_file(config.get_main_option("token_ini"))
settings = {}
load_into_settings(ini_file, settings)


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = settings["tokenserver.sqluri"]
    context.configure(url=url)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    url = settings["tokenserver.sqluri"]
    engine = create_engine(url, poolclass=NullPool)
    connection = engine.connect()
    context.configure(
        connection=connection,
    )

    try:
        with context.begin_transaction():
            context.run_migrations()
    finally:
        connection.close()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
