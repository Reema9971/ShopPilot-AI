import sqlite3
from pathlib import Path

DB_PATH = Path("data/shoppilot.db")


def get_connection():
    DB_PATH.parent.mkdir(exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_database():
    conn = get_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact TEXT NOT NULL,
            requirement TEXT NOT NULL,
            recommended_product TEXT,
            status TEXT DEFAULT 'New',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            contact TEXT NOT NULL,
            product TEXT NOT NULL,
            price REAL NOT NULL,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def create_lead(name, contact, requirement, recommended_product):
    conn = get_connection()

    conn.execute(
        """
        INSERT INTO leads
        (name, contact, requirement, recommended_product)
        VALUES (?, ?, ?, ?)
        """,
        (name, contact, requirement, recommended_product)
    )

    conn.commit()
    conn.close()


def create_order(customer_name, contact, product, price):
    conn = get_connection()

    conn.execute(
        """
        INSERT INTO orders
        (customer_name, contact, product, price)
        VALUES (?, ?, ?, ?)
        """,
        (customer_name, contact, product, price)
    )

    conn.commit()
    conn.close()


def get_leads():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM leads ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return rows


def get_orders():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM orders ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return rows