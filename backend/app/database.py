import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from backend.app.config import settings


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS payment_intents (
  id TEXT PRIMARY KEY,
  owner_id TEXT NOT NULL,
  recipient_name TEXT NOT NULL,
  recipient_email TEXT NOT NULL,
  amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
  currency TEXT NOT NULL CHECK(currency = 'USD'),
  purpose TEXT NOT NULL,
  condition_summary TEXT,
  status TEXT NOT NULL CHECK(status IN ('pending_approval','approved','processing','succeeded','failed','cancelled')),
  request_fingerprint TEXT NOT NULL,
  created_at TEXT NOT NULL,
  approved_at TEXT,
  executed_at TEXT,
  provider_transaction_id TEXT UNIQUE,
  idempotency_key TEXT UNIQUE,
  provider_payout_batch_id TEXT UNIQUE,
  failure_code TEXT
);
CREATE INDEX IF NOT EXISTS idx_intents_owner_created ON payment_intents(owner_id, created_at DESC);
CREATE TABLE IF NOT EXISTS audit_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  payment_intent_id TEXT NOT NULL REFERENCES payment_intents(id),
  event_type TEXT NOT NULL,
  actor_id TEXT,
  details TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_intent_created ON audit_events(payment_intent_id, created_at ASC);
"""


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    path = Path(settings.database_path)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        # Forward-compatible migration for existing SQLite databases.
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(payment_intents)").fetchall()}
        if "provider_payout_batch_id" not in columns:
            conn.execute("ALTER TABLE payment_intents ADD COLUMN provider_payout_batch_id TEXT")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_intents_provider_batch "
            "ON payment_intents(provider_payout_batch_id) WHERE provider_payout_batch_id IS NOT NULL"
        )
