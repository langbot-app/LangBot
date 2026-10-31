from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class OrderLine:
    sku: str
    quantity: int
    unit_price: Decimal | str | int | float


@dataclass(frozen=True)
class OrderRequest:
    order_id: str
    customer_tier: str
    tax_rate: Decimal | str | int | float
    lines: tuple[OrderLine, ...]


@dataclass(frozen=True)
class OrderResult:
    order_id: str
    status: str
    subtotal: str = "0.00"
    discount: str = "0.00"
    tax: str = "0.00"
    total: str = "0.00"
    error: str = ""
