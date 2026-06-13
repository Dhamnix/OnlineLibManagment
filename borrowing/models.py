from datetime import timedelta
from django.conf import settings
from django.db import models
from django.utils import timezone

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
