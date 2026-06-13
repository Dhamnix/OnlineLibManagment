from abc import ABC, abstractmethod
from typing import Dict, Any
from decimal import Decimal
from django.conf import settings
from django.db import transaction

from .models import Payment
from borrowing.models import Fine


class PaymentGateway(ABC):
    """Abstract payment gateway interface.

    Implementations must provide process_payment and optionally get_status.
    """

    @abstractmethod
    def process_payment(self, payment: Payment, **kwargs) -> Dict[str, Any]:
        """Process the payment and return a result dict.

        Expected result keys: {
            "success": bool,
            "external_id": Optional[str],
            "message": Optional[str],
            "metadata": Optional[dict]
        }
        """

    def get_status(self, external_id: str) -> Dict[str, Any]:
        """Optional: query gateway for payment status by external id."""
        return {"status": "unknown"}


class DummyGateway(PaymentGateway):
    """A simple gateway used for development and testing.

    It immediately marks payments successful. Replace this with a real
    gateway adapter (Stripe, PayPal, etc.) by implementing PaymentGateway.
    """

    def process_payment(self, payment: Payment, **kwargs) -> Dict[str, Any]:
        # Simulate external processing and return a success response
        return {
            "success": True,
            "external_id": f"DUMMY-{payment.pk}",
            "message": "Processed by DummyGateway",
            "metadata": {"processor": "dummy"},
        }

    def get_status(self, external_id: str) -> Dict[str, Any]:
        return {"status": "completed", "external_id": external_id}


def get_gateway() -> PaymentGateway:
    """Factory to obtain the configured gateway.

    Look up settings.PAYMENT_GATEWAY to allow swapping gateways later.
    It may hold an import path string to a gateway class. Fallback to
    DummyGateway when not configured.
    """
    gateway_path = getattr(settings, "PAYMENT_GATEWAY", None)
    if not gateway_path:
        return DummyGateway()

    # If PAYMENT_GATEWAY is a class or instance already
    if isinstance(gateway_path, PaymentGateway):
        return gateway_path

    if isinstance(gateway_path, type) and issubclass(gateway_path, PaymentGateway):
        return gateway_path()

    # If it's a dotted path, import
    try:
        module_path, class_name = gateway_path.rsplit(".", 1)
        module = __import__(module_path, fromlist=[class_name])
        cls = getattr(module, class_name)
        return cls()
    except Exception:
        # Fallback
        return DummyGateway()


def create_payment_for_fine(fine: Fine, user, amount: Decimal = None, metadata: dict = None) -> Payment:
    """Create a Payment record for a fine. Amount defaults to full fine amount.

    The returned Payment has status PENDING and should be processed by
    process_payment().
    """
    if amount is None:
        amount = fine.amount

    payment = Payment.objects.create(
        fine=fine,
        user=user,
        amount=amount,
        metadata=metadata or {},
    )
    return payment


def process_payment(payment: Payment, **gateway_kwargs) -> Dict[str, Any]:
    """Process a previously-created Payment using configured gateway.

    On success the Payment.status is updated to COMPLETED and the linked
    Fine.is_paid is set to True inside a transaction. On failure the
    Payment.status becomes FAILED. The return value is the gateway result
    dict.
    """
    gateway = get_gateway()
    result = gateway.process_payment(payment, **gateway_kwargs)

    success = bool(result.get("success"))
    external_id = result.get("external_id")
    metadata = result.get("metadata") or {}

    with transaction.atomic():
        # Refresh payment for safety
        payment.refresh_from_db()
        payment.external_id = external_id
        payment.metadata = {**(payment.metadata or {}), **metadata}
        if success:
            payment.status = Payment.Status.COMPLETED
            payment.save()

            # mark fine paid
            fine = payment.fine
            fine.is_paid = True
            fine.save()
        else:
            payment.status = Payment.Status.FAILED
            payment.save()

    return result


def get_payment_status(payment: Payment) -> Dict[str, Any]:
    """Return status information for a Payment, possibly querying the gateway."""
    gateway = get_gateway()
    if payment.external_id and hasattr(gateway, "get_status"):
        try:
            return gateway.get_status(payment.external_id)
        except Exception:
            return {"status": payment.status}
    return {"status": payment.status}
