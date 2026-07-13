from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from .models import Borrow, Fine
from notif.services import notify_fine


def calculate_fine_for_borrow(borrow):
    """Calculate the fine for a borrow record."""
    if not borrow.due_date:
        return Decimal("0.00")

    end_date = borrow.return_date if borrow.return_date else timezone.now()
    
    if end_date <= borrow.due_date:
        return Decimal("0.00")
        
    overdue_duration = end_date - borrow.due_date
    overdue_days = overdue_duration.days
    
    if overdue_days == 0 and overdue_duration.total_seconds() > 0:
        overdue_days = 1
        
    if overdue_days <= 0:
        return Decimal("0.00")
        
    fine_per_day = Decimal(str(getattr(settings, "FINE_PER_DAY", 1.00)))
    return Decimal(overdue_days) * fine_per_day


def create_or_update_fine_for_borrow(borrow):
    """Calculate and persist the fine for a borrow record if overdue."""
    amount = calculate_fine_for_borrow(borrow)
    if amount > 0:
        fine, created = Fine.objects.get_or_create(
            borrow=borrow,
            defaults={"user": borrow.user, "amount": amount, "is_paid": False}
        )
        if not created and not fine.is_paid:
            fine.amount = amount
            fine.save()
        
        if created:
            notify_fine(fine)
        
        return fine
    return None


def update_all_overdue_fines():
    """Update active fines for all overdue borrowings."""
    now = timezone.now()
    active_overdue = Borrow.objects.filter(
        status=Borrow.StatusChoices.BORROWED,
        due_date__lt=now
    )
    for borrow in active_overdue:
        create_or_update_fine_for_borrow(borrow)