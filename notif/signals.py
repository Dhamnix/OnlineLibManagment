from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from borrowing.models import Borrow, Reservation, Fine
from .services import (
    notify_borrow,
    notify_return,
    notify_reservation,
    notify_reservation_created,
    notify_fine,
    notify_fine_paid,
)


@receiver(pre_save, sender=Borrow)
def borrow_pre_save_handler(sender, instance, **kwargs):
    """Store previous status before save to detect changes."""
    if instance.pk:
        try:
            previous = Borrow.objects.get(pk=instance.pk)
            instance._previous_status = previous.status
        except Borrow.DoesNotExist:
            instance._previous_status = None
    else:
        instance._previous_status = None


@receiver(post_save, sender=Borrow)
def borrow_post_save_handler(sender, instance, created, **kwargs):
    """Send notification when a borrow is created or returned."""
    if created:
        notify_borrow(instance)
    
    elif hasattr(instance, '_previous_status'):
        if (instance._previous_status == Borrow.StatusChoices.BORROWED and 
            instance.status == Borrow.StatusChoices.RETURNED):
            notify_return(instance)


@receiver(pre_save, sender=Reservation)
def reservation_pre_save_handler(sender, instance, **kwargs):
    """Store previous status before save to detect changes."""
    if instance.pk:
        try:
            previous = Reservation.objects.get(pk=instance.pk)
            instance._previous_status = previous.status
        except Reservation.DoesNotExist:
            instance._previous_status = None
    else:
        instance._previous_status = None


@receiver(post_save, sender=Reservation)
def reservation_post_save_handler(sender, instance, created, **kwargs):
    """Send notification when reservation is created or status changes."""
    if created:
        notify_reservation_created(instance)
    
    elif hasattr(instance, '_previous_status'):
        if (instance.status == Reservation.StatusChoices.AVAILABLE and 
            instance._previous_status != Reservation.StatusChoices.AVAILABLE):
            notify_reservation(instance)
        
        if (instance.status == Reservation.StatusChoices.CANCELLED and 
            instance._previous_status != Reservation.StatusChoices.CANCELLED):
            from .services import notify_reservation_cancelled
            notify_reservation_cancelled(instance)


@receiver(post_save, sender=Fine)
def fine_post_save_handler(sender, instance, created, **kwargs):
    """Send notification when a fine is created or paid."""
    if created and instance.amount > 0:
        notify_fine(instance)
    elif not created and instance.is_paid:
        if hasattr(instance, '_previous_is_paid') and not instance._previous_is_paid:
            notify_fine_paid(instance)


@receiver(pre_save, sender=Fine)
def fine_pre_save_handler(sender, instance, **kwargs):
    """Store previous is_paid status before save to detect changes."""
    if instance.pk:
        try:
            previous = Fine.objects.get(pk=instance.pk)
            instance._previous_is_paid = previous.is_paid
        except Fine.DoesNotExist:
            instance._previous_is_paid = None
    else:
        instance._previous_is_paid = None