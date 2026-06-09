from django.core.exceptions import ValidationError
from django.db import models


class Book(models.Model):
    # Core catalog fields used for searching and displaying books.
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255)
    genre = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    # Publishing and identification metadata.
    publish_year = models.PositiveIntegerField()
    isbn = models.CharField(max_length=20, unique=True)

    # Inventory fields. available_copies is kept separate so borrowing can
    # decrement it without changing the library's owned copy count.
    total_copies = models.PositiveIntegerField(default=1)
    available_copies = models.PositiveIntegerField(default=1)

    # Stored under MEDIA_ROOT/book_covers/ by Django's file storage system.
    cover_image = models.ImageField(upload_to="book_covers/", blank=True)

    def __init__(self, *args, **kwargs):
        available_copies_was_provided = "available_copies" in kwargs
        super().__init__(*args, **kwargs)
        self._available_copies_was_provided = available_copies_was_provided

    def __setattr__(self, name, value):
        if name == "available_copies" and "_available_copies_was_provided" in self.__dict__:
            self.__dict__["_available_copies_was_provided"] = True
        super().__setattr__(name, value)

    class Meta:
        ordering = ["title"]
        verbose_name = "book"
        verbose_name_plural = "books"

    def clean(self):
        errors = {}

        if self.total_copies is not None and self.total_copies < 1:
            errors["total_copies"] = "Total copies must be at least 1."

        if self.available_copies is not None and self.available_copies < 0:
            errors["available_copies"] = "Available copies cannot be negative."

        if (
            self.total_copies is not None
            and self.available_copies is not None
            and self.available_copies > self.total_copies
        ):
            errors["available_copies"] = "Available copies cannot exceed total copies."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self._state.adding and not self._available_copies_was_provided:
            self.available_copies = self.total_copies

        # Enforce inventory consistency for code paths outside forms/admin.
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} by {self.author}"
