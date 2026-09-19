from collections.abc import Mapping

from .models import OrderLine


class Inventory:
    def __init__(self, stock: Mapping[str, int]):
        self._stock = dict(stock)

    def snapshot(self) -> dict[str, int]:
        return dict(self._stock)

    def reserve(self, lines: tuple[OrderLine, ...]) -> None:
        for line in lines:
            if line.sku not in self._stock:
                raise ValueError(f"unknown sku: {line.sku}")
            if self._stock[line.sku] < line.quantity:
                raise ValueError(f"insufficient stock: {line.sku}")
            self._stock[line.sku] -= line.quantity
