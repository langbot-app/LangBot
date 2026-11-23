from order_engine import Inventory, OrderLine, OrderProcessor, OrderRequest


def request(order_id, tier, tax, *lines):
    return OrderRequest(order_id, tier, tax, tuple(lines))


inventory = Inventory({"BOOK": 6, "PEN": 3})
processor = OrderProcessor(inventory)
orders = [
    request("c-3", "vip", "0.08", OrderLine("BOOK", 2, "12.50")),
    request("c-2", "standard", "0", OrderLine("PEN", 2, "1.005"), OrderLine("PEN", 2, "1.005")),
    request("c-1", "premium", "0.05", OrderLine("BOOK", 1, "20.00")),
]
results, report = processor.process_batch(orders)
assert [result.status for result in results] == ["accepted", "rejected", "accepted"]
assert report == {
    "accepted": 2,
    "rejected": 1,
    "revenue": "42.15",
    "orders": ["c-1", "c-2", "c-3"],
}
assert inventory.snapshot() == {"BOOK": 3, "PEN": 3}
assert processor.process(orders[0]) == results[0]
assert inventory.snapshot() == {"BOOK": 3, "PEN": 3}
print("ACCEPTANCE_PASS")
