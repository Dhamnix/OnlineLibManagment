from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Borrow, Reservation
from notifications.services import (
    send_borrow_notification,
    send_reserved_available_notification,
)


@receiver(post_save, sender=Borrow)
def borrow_post_save(sender, instance: Borrow, created, **kwargs):
    """When a Borrow record is created, notify the borrower."""
    if created:
        # Send confirmation email to borrower
        try:
            send_borrow_notification(instance)
        except Exception:
            # Keep signal handlers resilient. In production log the exception.
            pass


@receiver(pre_save, sender=Reservation)
def reservation_pre_save(sender, instance: Reservation, **kwargs):
    """Store previous status so post_save can detect transitions."""
    if instance.pk:
        try:
            previous = Reservation.objects.get(pk=instance.pk)
            instance._previous_status = previous.status
        except Reservation.DoesNotExist:
            instance._previous_status = None
    else:
        instance._previous_status = None


@receiver(post_save, sender=Reservation)
def reservation_post_save(sender, instance: Reservation, created, **kwargs):
    """Notify user when reservation status transitions to AVAILABLE."""
    # Only notify when status becomes AVAILABLE and it wasn't AVAILABLE before
    new_status = instance.status
    old_status = getattr(instance, "_previous_status", None)

    if new_status == Reservation.StatusChoices.AVAILABLE and old_status != Reservation.StatusChoices.AVAILABLE:
        try:
            send_reserved_available_notification(instance)
        except Exception:
            # Resilient to email failures
            pass
