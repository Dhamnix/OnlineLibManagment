from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from .models import Borrow, Fine


def calculate_fine_for_borrow(borrow):
    """Calculate the fine for a borrow record.
    
    If returned, calculate based on return_date. If still active,
    calculate based on current timezone.now().
    """
    if not borrow.due_date:
        return Decimal("0.00")

    end_date = borrow.return_date if borrow.return_date else timezone.now()
    
    if end_date <= borrow.due_date:
        return Decimal("0.00")
        
    overdue_duration = end_date - borrow.due_date
    overdue_days = overdue_duration.days
    
    # If overdue by some hours but days is 0, round up to 1 day
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
        return fine
    return None


def update_all_overdue_fines():
    """Service function to update active fines for all overdue borrowings.
    
    Can be run as a background cron job.
    """
    now = timezone.now()
    active_overdue = Borrow.objects.filter(
        status=Borrow.StatusChoices.BORROWED,
        due_date__lt=now
    )
    for borrow in active_overdue:
        create_or_update_fine_for_borrow(borrow)
