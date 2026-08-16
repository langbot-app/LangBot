from decimal import Decimal

from .models import OrderLine


CENT = Decimal("0.01")
DISCOUNT_RATES = {
    "standard": Decimal("0"),
    "vip": Decimal("0.10"),
    "premium": Decimal("0.15"),
}


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT)


def calculate_price(
    lines: tuple[OrderLine, ...], customer_tier: str, tax_rate: Decimal | str | int | float
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    discount_rate = DISCOUNT_RATES.get(customer_tier, Decimal("0"))
    subtotal = money(sum((Decimal(line.unit_price) * line.quantity for line in lines), Decimal("0")))
    tax = money(subtotal * Decimal(tax_rate))
    discount = money((subtotal + tax) * discount_rate)
    total = money(subtotal + tax - discount)
    return subtotal, discount, tax, total
