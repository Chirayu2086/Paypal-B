import sqlite3

from backend.app.config import settings
from backend.app.database import init_db


def test_existing_database_gets_payout_batch_migration(tmp_path, monkeypatch):
    database_path = tmp_path / "legacy.db"
    monkeypatch.setattr(settings, "database_path", str(database_path))

    # Simulate a database created before durable payout reconciliation existed.
    with sqlite3.connect(database_path) as conn:
        conn.execute(
            "CREATE TABLE payment_intents ("
            "id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, created_at TEXT NOT NULL)"
        )

    init_db()

    with sqlite3.connect(database_path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(payment_intents)")}
        indexes = {row[1] for row in conn.execute("PRAGMA index_list(payment_intents)")}

    assert "provider_payout_batch_id" in columns
    assert "idx_intents_provider_batch" in indexes
