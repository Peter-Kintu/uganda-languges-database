from dataclasses import dataclass
from decimal import Decimal
from uuid import uuid4


@dataclass
class QuoteResult:
    amount: Decimal
    currency: str
    eta_minutes: int


@dataclass
class DispatchResult:
    external_id: str
    tracking_url: str


class CourierAdapter:
    code = 'mock'

    def quote(self, *, order):
        return QuoteResult(amount=Decimal('5000.00'), currency=order.currency, eta_minutes=90)

    def dispatch(self, *, order, quote):
        shipment_id = f'{self.code}-{uuid4().hex[:12]}'
        return DispatchResult(external_id=shipment_id, tracking_url='')


class CourierRegistry:
    _adapters = {'mock': CourierAdapter()}

    @classmethod
    def get(cls, code):
        return cls._adapters.get(code, cls._adapters['mock'])
