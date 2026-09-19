from .inventory import Inventory
from .models import OrderRequest, OrderResult
from .pricing import calculate_price
from .report import build_report


class OrderProcessor:
    def __init__(self, inventory: Inventory):
        self.inventory = inventory

    def process(self, order: OrderRequest) -> OrderResult:
        self.inventory.reserve(order.lines)
        subtotal, discount, tax, total = calculate_price(order.lines, order.customer_tier, order.tax_rate)
        return OrderResult(
            order_id=order.order_id,
            status="accepted",
            subtotal=str(subtotal),
            discount=str(discount),
            tax=str(tax),
            total=str(total),
        )

    def process_batch(self, orders: list[OrderRequest]) -> tuple[list[OrderResult], dict[str, object]]:
        results = [self.process(order) for order in orders]
        return results, build_report(results)
