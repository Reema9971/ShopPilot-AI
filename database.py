import sqlite3
import csv
from pathlib import Path


DB_PATH = Path("data/shoppilot.db")
PRODUCTS_FILE = Path("products.csv")


def get_connection():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_database():
    conn = get_connection()

    # Products / Inventory
    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            description TEXT,
            features TEXT,
            stock INTEGER NOT NULL
        )
    """)

    # Leads
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

    # Orders
    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            contact TEXT NOT NULL,
            product TEXT NOT NULL,
            product_id INTEGER,
            price REAL NOT NULL,
            status TEXT DEFAULT 'Pending',
            razorpay_order_id TEXT,
            payment_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Safe migration for an older orders table.
    columns = {
        row[1]
        for row in conn.execute(
            "PRAGMA table_info(orders)"
        ).fetchall()
    }

    if "product_id" not in columns:
        conn.execute(
            "ALTER TABLE orders ADD COLUMN product_id INTEGER"
        )
        conn.execute(
            """
            UPDATE orders
            SET product_id = (
                SELECT id
                FROM products
                WHERE products.name = orders.product
                LIMIT 1
            )
            WHERE product_id IS NULL
            """
        )

    if "razorpay_order_id" not in columns:
        conn.execute(
            "ALTER TABLE orders ADD COLUMN razorpay_order_id TEXT"
        )

    if "payment_id" not in columns:
        conn.execute(
            "ALTER TABLE orders ADD COLUMN payment_id TEXT"
        )

    # Seed products only when the table is empty.
    product_count = conn.execute(
        "SELECT COUNT(*) FROM products"
    ).fetchone()[0]

    if product_count == 0:
        with open(PRODUCTS_FILE, "r", encoding="utf-8") as file:
            reader = csv.DictReader(file)

            for product in reader:
                conn.execute(
                    """
                    INSERT INTO products
                    (id, name, category, price, description, features, stock)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(product["id"]),
                        product["name"],
                        product["category"],
                        float(product["price"]),
                        product["description"],
                        product["features"],
                        int(product["stock"]),
                    )
                )

    conn.execute(
        """
        UPDATE orders
        SET product_id = (
            SELECT id
            FROM products
            WHERE products.name = orders.product
            LIMIT 1
        )
        WHERE product_id IS NULL
        """
    )

    conn.commit()
    conn.close()


# =========================================================
# PRODUCTS / INVENTORY
# =========================================================

def get_products():
    conn = get_connection()

    rows = conn.execute(
        """
        SELECT id, name, category, price,
               description, features, stock
        FROM products
        ORDER BY id
        """
    ).fetchall()

    conn.close()
    return rows


def reduce_stock(product_id, quantity=1):
    conn = get_connection()

    cursor = conn.execute(
        """
        UPDATE products
        SET stock = stock - ?
        WHERE id = ?
          AND stock >= ?
        """,
        (quantity, product_id, quantity)
    )

    conn.commit()
    success = cursor.rowcount > 0
    conn.close()

    return success


# =========================================================
# LEADS
# =========================================================

def create_lead(
    name,
    contact,
    requirement,
    recommended_product
):
    conn = get_connection()

    conn.execute(
        """
        INSERT INTO leads
        (name, contact, requirement, recommended_product)
        VALUES (?, ?, ?, ?)
        """,
        (
            name,
            contact,
            requirement,
            recommended_product
        )
    )

    conn.commit()
    conn.close()


def get_leads():
    conn = get_connection()

    rows = conn.execute(
        """
        SELECT
            id,
            name,
            contact,
            requirement,
            recommended_product,
            created_at
        FROM leads
        ORDER BY created_at DESC
        """
    ).fetchall()

    conn.close()
    return rows


# =========================================================
# ORDERS / PAYMENTS
# =========================================================

def create_order(
    customer_name,
    contact,
    product,
    price,
    status="Pending",
    razorpay_order_id=None,
    payment_id=None,
    product_id=None,
):
    conn = get_connection()

    cursor = conn.execute(
        """
        INSERT INTO orders
        (
            customer_name,
            contact,
            product,
            product_id,
            price,
            status,
            razorpay_order_id,
            payment_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            customer_name,
            contact,
            product,
            product_id,
            price,
            status,
            razorpay_order_id,
            payment_id
        )
    )

    order_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return order_id


def get_order_by_razorpay_id(razorpay_order_id):
    conn = get_connection()

    row = conn.execute(
        """
        SELECT
            id,
            customer_name,
            contact,
            product,
            price,
            status,
            razorpay_order_id,
            payment_id,
            created_at,
            product_id
        FROM orders
        WHERE razorpay_order_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (razorpay_order_id,)
    ).fetchone()

    conn.close()
    return row


def complete_order_payment(razorpay_order_id, payment_id, quantity=1):
    """
    Atomically complete a paid order.

    Rules:
    1. If already Paid, do nothing and never reduce stock again.
    2. Find the product connected to the order.
    3. Require stock >= quantity.
    4. Reduce stock by the ordered quantity.
    5. Mark the SAME order Paid and save payment_id.
    """

    print("COMPLETE PAYMENT CALLED:", razorpay_order_id, payment_id, quantity)

    conn = get_connection()

    try:
        conn.execute("BEGIN IMMEDIATE")

        order = conn.execute(
            """
            SELECT id, product, product_id, price, status
            FROM orders
            WHERE razorpay_order_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (razorpay_order_id,)
        ).fetchone()

        if not order:
            conn.rollback()
            return False, "Local order not found."

        order_id, product_name, product_id, _, status = order

        # Already paid → do not reduce stock again
        if status == "Paid":
            conn.commit()
            return True, "Payment already recorded."

        # Find product
        if product_id is not None:
            product = conn.execute(
                """
                SELECT id, stock
                FROM products
                WHERE id = ?
                LIMIT 1
                """,
                (product_id,)
            ).fetchone()
        else:
            product = conn.execute(
                """
                SELECT id, stock
                FROM products
                WHERE name = ?
                LIMIT 1
                """,
                (product_name,)
            ).fetchone()

        if not product:
            conn.rollback()
            return False, "Product not found."

        product_id, stock = product

        # Make sure quantity is valid
        quantity = int(quantity)

        if quantity <= 0:
            conn.rollback()
            return False, "Invalid quantity."

        # Check enough stock
        if stock < quantity:
            conn.rollback()
            return False, f"Insufficient stock. Available: {stock}"

        # Reduce stock by ordered quantity
        updated_stock = conn.execute(
            """
            UPDATE products
            SET stock = stock - ?
            WHERE id = ?
              AND stock >= ?
            """,
            (quantity, product_id, quantity)
        ).rowcount

        if updated_stock != 1:
            conn.rollback()
            return False, "Stock could not be reduced."

        # Mark SAME order as Paid
        updated_order = conn.execute(
            """
            UPDATE orders
            SET status = 'Paid',
                product_id = ?,
                payment_id = ?
            WHERE id = ?
              AND status != 'Paid'
            """,
            (product_id, payment_id, order_id)
        ).rowcount

        if updated_order != 1:
            conn.rollback()
            return False, "Order could not be updated."

        conn.commit()

        return True, payment_id

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def mark_order_paid(razorpay_order_id, payment_id):
    """
    Backward-compatible wrapper.
    """
    success, _ = complete_order_payment(
        razorpay_order_id,
        payment_id
    )
    return success


def get_orders():
    conn = get_connection()

    rows = conn.execute(
        """
        SELECT
            id,
            customer_name,
            contact,
            product,
            price,
            status,
            razorpay_order_id,
            payment_id,
            created_at,
            product_id
        FROM orders
        ORDER BY created_at DESC
        """
    ).fetchall()

    conn.close()
    return rows