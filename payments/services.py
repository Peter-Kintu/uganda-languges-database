import logging
import os
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class NylonPaymentResult:
    reference: str
    transaction_id: str = ""
    status: str = "pending"
    message: str = ""
    raw: Any = None


def _nylon_client():
    from nylonpay import create_nylon_pay

    api_key = os.getenv("NYLON_API_KEY", "").strip()
    api_secret = os.getenv("NYLON_API_SECRET", "").strip()
    if not api_key or not api_secret:
        raise RuntimeError("NYLON_API_KEY and NYLON_API_SECRET must be configured.")

    return create_nylon_pay(
        api_key=api_key,
        api_secret=api_secret,
    )


def collect_payment(*, amount, currency, customer_name, customer_phone, description, reference):
    """Start a Nylon collection and wait for its terminal SDK result."""
    if not customer_phone:
        raise ValueError("A customer phone number is required for Nylon Pay.")

    payment = _nylon_client().collect_payment(
        amount=int(amount),
        currency=currency,
        customer={"name": customer_name, "phone_number": customer_phone},
        description=description,
        reference=reference,
    )
    events = []
    payment.on("failed", lambda event: events.append(event))
    payment.on("cancelled", lambda event: events.append(event))
    payment.on("error", lambda event: events.append(event))
    transaction = payment.wait()
    if not transaction:
        event = events[-1] if events else None
        sdk_status = str(getattr(payment, "status", "pending") or "pending").lower()
        status = {
            "successful": "paid",
            "failed": "failed",
            "cancelled": "cancelled",
        }.get(sdk_status, "pending")
        return NylonPaymentResult(
            reference=reference,
            status=status,
            message=str(getattr(event, "error", "") or ""),
            raw=payment,
        )

    return NylonPaymentResult(
        reference=str(getattr(transaction, "reference", reference) or reference),
        transaction_id=str(getattr(transaction, "id", "") or ""),
        status="paid",
        raw=transaction,
    )


def get_payment_status(reference):
    """Fetch one current Nylon status for a previously created UUID reference."""
    result = _nylon_client().get_status(reference=reference)
    if not result.is_ok:
        return NylonPaymentResult(reference=reference, status="pending", message=str(result.error or ""))

    status = str(getattr(result.value, "status", "pending") or "pending").lower()
    return NylonPaymentResult(
        reference=reference,
        status={
            "successful": "paid",
            "completed": "paid",
            "paid": "paid",
            "failed": "failed",
            "cancelled": "cancelled",
        }.get(status, "pending"),
        message=str(getattr(result.value, "failure_reason", "") or ""),
        raw=result.value,
    )
