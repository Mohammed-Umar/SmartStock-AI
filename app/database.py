import sqlite3
import os
from contextlib import contextmanager
from typing import Generator

DB_PATH = os.environ.get("SMARTSTOCK_DB_PATH", "smartstock.db")


def get_db():
    """Returns a new sqlite3 connection with Row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def get_db_context() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for database transactions."""
    conn = get_db()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initializes database tables and indexes."""
    with get_db_context() as conn:
        cursor = conn.cursor()

        # Items Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                current_quantity REAL NOT NULL,
                unit TEXT NOT NULL,
                min_threshold REAL NOT NULL,
                optimal_quantity REAL NOT NULL,
                cost_per_unit REAL NOT NULL,
                purchase_date TEXT NOT NULL,
                expiry_date TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)

        # Consumption Logs Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS consumption_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                quantity_consumed REAL NOT NULL,
                consumption_date TEXT NOT NULL,
                reason TEXT DEFAULT 'Normal Usage',
                is_waste INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
            );
        """)

        # Purchase History Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchase_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER,
                item_name TEXT NOT NULL,
                quantity REAL NOT NULL,
                unit TEXT NOT NULL,
                cost REAL NOT NULL,
                purchase_date TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE SET NULL
            );
        """)

        # Shopping List Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shopping_list (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER,
                item_name TEXT NOT NULL,
                category TEXT NOT NULL,
                quantity_needed REAL NOT NULL,
                unit TEXT NOT NULL,
                estimated_cost REAL NOT NULL,
                urgency TEXT NOT NULL DEFAULT 'RECOMMENDED',
                reason TEXT NOT NULL,
                is_purchased INTEGER DEFAULT 0,
                auto_generated INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE SET NULL
            );
        """)

        # Anomalies Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS anomalies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                consumption_log_id INTEGER,
                anomaly_score REAL NOT NULL,
                severity TEXT NOT NULL,
                description TEXT NOT NULL,
                detected_at TEXT NOT NULL,
                status TEXT DEFAULT 'UNRESOLVED',
                FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE,
                FOREIGN KEY (consumption_log_id) REFERENCES consumption_logs(id) ON DELETE SET NULL
            );
        """)

        # Indexes for query performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_category ON items(category);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_consumption_item ON consumption_logs(item_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_consumption_date ON consumption_logs(consumption_date);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_shopping_purchased ON shopping_list(is_purchased);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_anomalies_status ON anomalies(status);")


def dict_from_row(row: sqlite3.Row) -> dict:
    """Helper to convert sqlite3.Row to a standard python dict."""
    return dict(row) if row else {}
