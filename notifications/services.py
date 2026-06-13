from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from borrowing.models import Borrow, Reservation


DEFAULT_FROM_EMAIL = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@library.com")


def send_email(subject: str, body: str, to: list, html_body: str = None):
    """Send an email using Django's configured email backend.

    This wrapper uses EmailMultiAlternatives so an HTML version can be
    attached. The function returns True on success (or silent failure)
    and False on exception.
    """
    if not to:
        return False

    msg = EmailMultiAlternatives(subject=subject, body=body, from_email=DEFAULT_FROM_EMAIL, to=to)
    if html_body:
        msg.attach_alternative(html_body, "text/html")

    try:
        msg.send(fail_silently=True)
        return True
    except Exception:
        # In production code, log the exception here.
        return False


def send_borrow_notification(borrow: Borrow):
    """Notify the user that a book has been borrowed successfully."""
    user = borrow.user
    book = borrow.book
    subject = f"Book Borrowed: {book.title}"
    body = (
        f"Hello {user.username},\n\n"
        f"You have successfully borrowed '{book.title}' by {book.author}.\n"
        f"Borrow date: {borrow.borrow_date.strftime('%Y-%m-%d %H:%M')}\n"
        f"Due date: {borrow.due_date.strftime('%Y-%m-%d %H:%M')}\n\n"
        f"Please return the book by the due date to avoid fines.\n\n"
        f"Thank you,\nYour Library"
    )

    return send_email(subject, body, [user.email])


def send_reserved_available_notification(reservation: Reservation):
    """Notify a user that their reserved book is now available."""
    user = reservation.user
    book = reservation.book
    subject = f"Reserved Book Available: {book.title}"
    body = (
        f"Hello {user.username},\n\n"
        f"Good news — the book you reserved ('{book.title}') is now available for pickup.\n"
        f"Please visit the library within the next few days to borrow it.\n\n"
        f"Thank you,\nYour Library"
    )

    return send_email(subject, body, [user.email])


def send_due_approaching_notifications(days: int = 2):
    """Send notifications for borrowings that are approaching their due date.

    This function is intended to be called by a daily cron or periodic task.
    It finds Borrow records with status BORROWED and due_date between now and
    now + days and sends a reminder to the borrower.
    """
    now = timezone.now()
    window_end = now + timezone.timedelta(days=days)

    borrows = Borrow.objects.filter(
        status=Borrow.StatusChoices.BORROWED,
        due_date__gt=now,
        due_date__lte=window_end,
    ).select_related("user", "book")

    sent = 0
    for b in borrows:
        subject = f"Due Date Approaching: {b.book.title}"
        body = (
            f"Hello {b.user.username},\n\n"
            f"This is a reminder that the book '{b.book.title}' is due on {b.due_date.strftime('%Y-%m-%d %H:%M')}.\n"
            f"Please return it by the due date to avoid fines.\n\n"
            f"Thank you,\nYour Library"
        )
        if send_email(subject, body, [b.user.email]):
            sent += 1

    return sent


def send_overdue_notifications():
    """Send notifications for borrowings that are overdue.

    Intended to be called regularly (e.g., daily). It will notify users whose
    borrowings have passed the due_date and still have status BORROWED.
    """
    now = timezone.now()
    borrows = Borrow.objects.filter(status=Borrow.StatusChoices.BORROWED, due_date__lt=now).select_related(
        "user", "book"
    )

    sent = 0
    for b in borrows:
        subject = f"Overdue Notice: {b.book.title}"
        body = (
            f"Hello {b.user.username},\n\n"
            f"Our records show that the book '{b.book.title}' was due on {b.due_date.strftime('%Y-%m-%d %H:%M')} and is now overdue.\n"
            f"Please return it as soon as possible to minimize fines.\n\n"
            f"If you have returned the book, please ignore this message.\n\n"
            f"Thank you,\nYour Library"
        )
        if send_email(subject, body, [b.user.email]):
            sent += 1

    return sent
