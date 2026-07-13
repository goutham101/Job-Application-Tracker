import os

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost/jobtracker")

# open=False: the pool connects during FastAPI startup, not at import time,
# so tests can point DATABASE_URL at the test database first.
pool = ConnectionPool(DATABASE_URL, kwargs={"row_factory": dict_row}, open=False)


def get_conn():
    """FastAPI dependency: pooled connection, committed on success."""
    with pool.connection() as conn:
        yield conn
