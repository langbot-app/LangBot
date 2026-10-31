from decimal import Decimal

from .models import OrderResult


def build_report(results: list[OrderResult]) -> dict[str, object]:
    accepted = [result for result in results if result.status == "accepted"]
    rejected = [result for result in results if result.status == "rejected"]
    revenue = sum((Decimal(result.total) for result in results), Decimal("0"))
    return {
        "accepted": len(accepted),
        "rejected": len(rejected),
        "revenue": str(revenue),
        "orders": [result.order_id for result in results],
    }
