from datetime import timedelta
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError

from books.models import Book


class Borrow(models.Model):
    class StatusChoices(models.TextChoices):
        PENDING = "PENDING", "Pending Request"
        BORROWED = "BORROWED", "Borrowed"
        RETURNED = "RETURNED", "Returned"
        REJECTED = "REJECTED", "Rejected"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="borrowings",
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name="borrowings",
    )
    request_date = models.DateTimeField(default=timezone.now)
    borrow_date = models.DateTimeField(null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    return_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=10,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_borrowings",
    )
    rejected_reason = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-request_date"]

    def __str__(self):
        return f"{self.user.username} - {self.book.title} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        # Only auto-set due_date when status is BORROWED and due_date is not set
        if self.status == self.StatusChoices.BORROWED and self.borrow_date and not self.due_date:
            days = getattr(settings, 'BORROWING_DAYS', 14)
            self.due_date = self.borrow_date + timedelta(days=days)
        super().save(*args, **kwargs)


class Reservation(models.Model):
    class StatusChoices(models.TextChoices):
        PENDING = "PENDING", "Pending"
        AVAILABLE = "AVAILABLE", "Available"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reservations",
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name="reservations",
    )
    reservation_date = models.DateTimeField(default=timezone.now)
    status = models.CharField(
        max_length=10,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING,
    )

    class Meta:
        ordering = ["reservation_date"]

    def __str__(self):
        return f"{self.user.username} reserved {self.book.title} ({self.status})"

    def clean(self):
        super().clean()
        # Enforce that pending reservations can only be created when available_copies is 0
        if self.pk is None and self.status == self.StatusChoices.PENDING and self.book.available_copies > 0:
            raise ValidationError("You can only reserve books that are currently out of stock.")


class Fine(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="fines",
    )
    borrow = models.OneToOneField(
        Borrow,
        on_delete=models.CASCADE,
        related_name="fine",
    )
    amount = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    is_paid = models.BooleanField(default=False)

    class Meta:
        ordering = ["is_paid", "-amount"]

    def __str__(self):
        status = "Paid" if self.is_paid else "Unpaid"
        return f"Fine of {self.amount} for {self.user.username} ({status})"
