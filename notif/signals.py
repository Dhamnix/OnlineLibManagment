# notif/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta

from borrowing.models import Borrow, Reservation, Fine
from .services import (
    notify_borrow,
    notify_return,
    notify_reservation,
    notify_fine,
    notify_reminder,
    notify_overdue
)


@receiver(post_save, sender=Borrow)
def borrow_notification_handler(sender, instance, created, **kwargs):
    """Send notification when a borrow is created."""
    if created:
        notify_borrow(instance)


@receiver(post_save, sender=Borrow)
def return_notification_handler(sender, instance, created, **kwargs):
    """Send notification when a borrow is returned."""
    if not created and instance.status == Borrow.StatusChoices.RETURNED:
        # Check if status was changed from BORROWED to RETURNED
        if hasattr(instance, '_previous_status') and instance._previous_status == Borrow.StatusChoices.BORROWED:
            notify_return(instance)


@receiver(post_save, sender=Reservation)
def reservation_notification_handler(sender, instance, created, **kwargs):
    """Send notification when reservation status changes to AVAILABLE."""
    if not created and instance.status == Reservation.StatusChoices.AVAILABLE:
        if hasattr(instance, '_previous_status') and instance._previous_status != Reservation.StatusChoices.AVAILABLE:
            notify_reservation(instance)


@receiver(post_save, sender=Fine)
def fine_notification_handler(sender, instance, created, **kwargs):
    """Send notification when a fine is created."""
    if created:
        notify_fine(instance)