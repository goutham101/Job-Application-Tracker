"""Apply numbered SQL migrations in db/migrations/ that haven't run yet.

Usage: python db/migrate.py [--database-url URL]
Falls back to $DATABASE_URL, then postgresql://localhost/jobtracker.
"""

import argparse
import os
import sys
from pathlib import Path

import psycopg

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
DEFAULT_URL = os.environ.get("DATABASE_URL", "postgresql://localhost/jobtracker")


def migrate(database_url: str) -> list[str]:
    """Apply pending migrations, each in its own transaction. Returns applied filenames."""
    applied = []
    with psycopg.connect(database_url) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS schema_migrations (
                   filename   TEXT PRIMARY KEY,
                   applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
               )"""
        )
        conn.commit()

        done = {
            row[0]
            for row in conn.execute("SELECT filename FROM schema_migrations").fetchall()
        }
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name in done:
                continue
            conn.execute(path.read_text())
            conn.execute(
                "INSERT INTO schema_migrations (filename) VALUES (%s)", (path.name,)
            )
            conn.commit()
            applied.append(path.name)
    return applied


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=DEFAULT_URL)
    args = parser.parse_args()
    names = migrate(args.database_url)
    if names:
        print(f"Applied: {', '.join(names)}")
    else:
        print("Nothing to apply.")
    sys.exit(0)
