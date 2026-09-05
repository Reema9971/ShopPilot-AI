import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

import database


class OrderPaymentRegressionTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.temp_db = Path(self.temp_dir) / "shoppilot.db"
        self.original_db_path = database.DB_PATH
        database.DB_PATH = self.temp_db
        database.init_database()

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_complete_order_payment_updates_inventory_and_order_record(self):
        order_id = database.create_order(
            customer_name="Alice",
            contact="alice@example.com",
            product="AirPods Pro 2",
            product_id=1,
            price=24999,
            status="Pending",
            razorpay_order_id="order_123",
        )

        self.assertIsInstance(order_id, int)

        success, payment_id = database.complete_order_payment(
            "order_123",
            "pay_123",
        )

        self.assertTrue(success)
        self.assertEqual(payment_id, "pay_123")

        with sqlite3.connect(self.temp_db) as conn:
            order = conn.execute(
                "SELECT status, payment_id, product_id FROM orders WHERE id = ?",
                (order_id,),
            ).fetchone()
            product = conn.execute(
                "SELECT stock FROM products WHERE id = ?",
                (1,),
            ).fetchone()

        self.assertEqual(order[0], "Paid")
        self.assertEqual(order[1], "pay_123")
        self.assertEqual(order[2], 1)
        self.assertEqual(product[0], 24)


if __name__ == "__main__":
    unittest.main()
