# notif/management/commands/test_all_notifications.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from books.models import Book
from borrowing.models import Borrow, Reservation, Fine
from notif.services import (
    notify_borrow, 
    notify_return, 
    notify_reservation,
    notify_reservation_created,
    notify_fine,
    notify_fine_paid,
    notify_reminder,
    notify_overdue,
    notify_welcome,
    create_notification
)
from notif.models import Notification

User = get_user_model()

class Command(BaseCommand):
    help = 'Test all types of notifications'

    def handle(self, *args, **options):
        user = User.objects.first()
        if not user:
            self.stdout.write(self.style.ERROR('❌ No user found! Please create a user first.'))
            return

        book = Book.objects.first()
        if not book:
            self.stdout.write(self.style.ERROR('❌ No book found! Please create a book first.'))
            return

        self.stdout.write(self.style.SUCCESS(f'\n📢 Testing all notification types for user: {user.username}'))
        self.stdout.write(f'   📖 Book: {book.title}\n')

        # 1. WELCOME notification
        notify_welcome(user)
        self.stdout.write(self.style.SUCCESS('  ✅ WELCOME notification sent'))

        # 2. BORROW notification
        borrow = Borrow.objects.create(
            user=user,
            book=book,
            borrow_date=timezone.now(),
            due_date=timezone.now() + timedelta(days=14),
            status=Borrow.StatusChoices.BORROWED
        )
        notify_borrow(borrow)
        self.stdout.write(self.style.SUCCESS('  ✅ BORROW notification sent'))

        # 3. REMINDER notification (3 days left)
        notify_reminder(borrow, 3)
        self.stdout.write(self.style.SUCCESS('  ✅ REMINDER (3 days) notification sent'))

        # 4. REMINDER notification (1 day left)
        notify_reminder(borrow, 1)
        self.stdout.write(self.style.SUCCESS('  ✅ REMINDER (1 day) notification sent'))

        # 5. OVERDUE notification
        borrow.due_date = timezone.now() - timedelta(days=5)
        borrow.save()
        notify_overdue(borrow)
        self.stdout.write(self.style.SUCCESS('  ✅ OVERDUE notification sent'))

        # 6. RETURN notification
        borrow.status = Borrow.StatusChoices.RETURNED
        borrow.return_date = timezone.now()
        borrow.save()
        notify_return(borrow)
        self.stdout.write(self.style.SUCCESS('  ✅ RETURN notification sent'))

        # 7. RESERVATION CREATED notification
        reservation = Reservation.objects.create(
            user=user,
            book=book,
            status=Reservation.StatusChoices.PENDING
        )
        notify_reservation_created(reservation)
        self.stdout.write(self.style.SUCCESS('  ✅ RESERVATION CREATED notification sent'))

        # 8. RESERVATION AVAILABLE notification
        reservation.status = Reservation.StatusChoices.AVAILABLE
        reservation.save()
        notify_reservation(reservation)
        self.stdout.write(self.style.SUCCESS('  ✅ RESERVATION AVAILABLE notification sent'))

        # 9. FINE notification
        fine = Fine.objects.create(
            user=user,
            borrow=borrow,
            amount=5.00,
            is_paid=False
        )
        notify_fine(fine)
        self.stdout.write(self.style.SUCCESS('  ✅ FINE notification sent'))

        # 10. FINE PAID notification
        fine.is_paid = True
        fine.save()
        notify_fine_paid(fine)
        self.stdout.write(self.style.SUCCESS('  ✅ FINE PAID notification sent'))

        # 11. SYSTEM notification
        create_notification(
            user=user,
            notification_type=Notification.Type.SYSTEM,
            title='⚙️ System Test Notification',
            message='This is a test system notification.',
            link='/'
        )
        self.stdout.write(self.style.SUCCESS('  ✅ SYSTEM notification sent'))

        total = Notification.objects.filter(user=user).count()
        self.stdout.write(self.style.SUCCESS(f'\n✅ All {total} notifications sent successfully!'))
        self.stdout.write(f'   📍 Visit: http://127.0.0.1:8000/notif/ to see them')