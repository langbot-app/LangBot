import unittest
from decimal import Decimal

from order_engine import Inventory, OrderLine, OrderProcessor, OrderRequest
from order_engine.pricing import calculate_price
from order_engine.report import build_report
from order_engine.models import OrderResult


def order(order_id, lines, tier="standard", tax="0"):
    return OrderRequest(order_id, tier, tax, tuple(lines))


class PricingTests(unittest.TestCase):
    def test_standard_total(self):
        values = calculate_price((OrderLine("A", 2, "10.00"),), "standard", "0.08")
        self.assertEqual(tuple(map(str, values)), ("20.00", "0.00", "1.60", "21.60"))

    def test_vip_discount_precedes_tax(self):
        values = calculate_price((OrderLine("A", 2, "25.00"),), "vip", "0.10")
        self.assertEqual(tuple(map(str, values)), ("50.00", "5.00", "4.50", "49.50"))

    def test_round_half_up_and_string_conversion(self):
        values = calculate_price((OrderLine("A", 1, 1.005),), "standard", "0")
        self.assertEqual(str(values[0]), "1.01")

    def test_unknown_tier_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown customer tier"):
            calculate_price((OrderLine("A", 1, "1"),), "wholesale", "0")


class InventoryTests(unittest.TestCase):
    def test_reservation_is_atomic(self):
        inventory = Inventory({"A": 3, "B": 1})
        with self.assertRaisesRegex(ValueError, "insufficient stock: B"):
            inventory.reserve((OrderLine("A", 2, "1"), OrderLine("B", 2, "1")))
        self.assertEqual(inventory.snapshot(), {"A": 3, "B": 1})

    def test_duplicate_skus_are_aggregated(self):
        inventory = Inventory({"A": 3})
        with self.assertRaisesRegex(ValueError, "insufficient stock: A"):
            inventory.reserve((OrderLine("A", 2, "1"), OrderLine("A", 2, "1")))
        self.assertEqual(inventory.snapshot(), {"A": 3})

    def test_successful_reservation_decrements_aggregate(self):
        inventory = Inventory({"A": 5})
        inventory.reserve((OrderLine("A", 2, "1"), OrderLine("A", 1, "1")))
        self.assertEqual(inventory.snapshot(), {"A": 2})

    def test_quantity_must_be_positive_integer(self):
        for bad_quantity in (0, -1, 1.5, True):
            with self.subTest(quantity=bad_quantity):
                inventory = Inventory({"A": 5})
                with self.assertRaisesRegex(ValueError, "positive integer"):
                    inventory.reserve((OrderLine("A", bad_quantity, "1"),))
                self.assertEqual(inventory.snapshot(), {"A": 5})


class ServiceTests(unittest.TestCase):
    def test_success_is_idempotent(self):
        inventory = Inventory({"A": 5})
        processor = OrderProcessor(inventory)
        request = order("same", [OrderLine("A", 2, "4.00")])
        self.assertEqual(processor.process(request), processor.process(request))
        self.assertEqual(inventory.snapshot(), {"A": 3})

    def test_failed_order_is_not_cached(self):
        inventory = Inventory({"A": 1})
        processor = OrderProcessor(inventory)
        with self.assertRaises(ValueError):
            processor.process(order("retry", [OrderLine("A", 2, "1")]))
        accepted = processor.process(order("retry", [OrderLine("A", 1, "1")]))
        self.assertEqual(accepted.status, "accepted")
        self.assertEqual(inventory.snapshot(), {"A": 0})

    def test_batch_continues_after_rejection(self):
        processor = OrderProcessor(Inventory({"A": 2}))
        results, report = processor.process_batch([
            order("ok-2", [OrderLine("A", 1, "3")]),
            order("bad", [OrderLine("MISSING", 1, "5")]),
            order("ok-1", [OrderLine("A", 1, "7")]),
        ])
        self.assertEqual([item.status for item in results], ["accepted", "rejected", "accepted"])
        self.assertIn("unknown sku", results[1].error)
        self.assertEqual(report["accepted"], 2)
        self.assertEqual(report["rejected"], 1)

    def test_report_is_sorted_and_accepted_revenue_only(self):
        report = build_report([
            OrderResult("z-order", "accepted", total="2.50"),
            OrderResult("a-rejected", "rejected", total="999.00", error="no"),
            OrderResult("m-order", "accepted", total="1.25"),
        ])
        self.assertEqual(report, {
            "accepted": 2,
            "rejected": 1,
            "revenue": "3.75",
            "orders": ["a-rejected", "m-order", "z-order"],
        })


if __name__ == "__main__":
    unittest.main()
