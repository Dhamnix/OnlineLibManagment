from datetime import timedelta
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError

from books.models import Book


class Borrow(models.Model):
    class StatusChoices(models.TextChoices):
        BORROWED = "BORROWED", "Borrowed"
        RETURNED = "RETURNED", "Returned"

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
    borrow_date = models.DateTimeField(default=timezone.now)
    due_date = models.DateTimeField()
    return_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=10,
        choices=StatusChoices.choices,
        default=StatusChoices.BORROWED,
    )

    class Meta:
        ordering = ["-borrow_date"]

    def __str__(self):
        return f"{self.user.username} borrowed {self.book.title}"

    def save(self, *args, **kwargs):
        if not self.due_date:
            # Default due date to 14 days from borrow date
            self.due_date = self.borrow_date + timedelta(days=14)
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
