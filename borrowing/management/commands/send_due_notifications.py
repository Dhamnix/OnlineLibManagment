# borrowing/management/commands/send_due_notifications.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from borrowing.models import Borrow
from notif.services import notify_reminder, notify_overdue
from notif.models import Notification


class Command(BaseCommand):
    help = 'Send due date reminders for borrowings'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without sending actual notifications',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        now = timezone.now()
        today = now.date()
        
        # Borrowings due in 3 days
        borrowings_3_days = Borrow.objects.filter(
            status=Borrow.StatusChoices.BORROWED,
            due_date__date=today + timedelta(days=3)
        )
        
        # Borrowings due in 1 day
        borrowings_1_day = Borrow.objects.filter(
            status=Borrow.StatusChoices.BORROWED,
            due_date__date=today + timedelta(days=1)
        )
        
        # Borrowings due today
        borrowings_today = Borrow.objects.filter(
            status=Borrow.StatusChoices.BORROWED,
            due_date__date=today
        )
        
        # Borrowings overdue
        overdue_borrowings = Borrow.objects.filter(
            status=Borrow.StatusChoices.BORROWED,
            due_date__date__lt=today
        )

        if dry_run:
            self.stdout.write("🔍 DRY RUN - No notifications will be sent")
            self.stdout.write(f"📅 Due in 3 days: {borrowings_3_days.count()}")
            self.stdout.write(f"📅 Due in 1 day: {borrowings_1_day.count()}")
            self.stdout.write(f"📅 Due today: {borrowings_today.count()}")
            self.stdout.write(f"⚠️ Overdue: {overdue_borrowings.count()}")
            return

        # Send notifications
        for borrow in borrowings_3_days:
            # Check if notification already sent
            existing = Notification.objects.filter(
                user=borrow.user,
                title__icontains="Due in 3 days",
                created_at__date=today
            ).exists()
            if not existing:
                notify_reminder(borrow, 3)
                self.stdout.write(f"✅ Reminder sent to {borrow.user.username} for {borrow.book.title} (3 days)")

        for borrow in borrowings_1_day:
            existing = Notification.objects.filter(
                user=borrow.user,
                title__icontains="Due tomorrow",
                created_at__date=today
            ).exists()
            if not existing:
                notify_reminder(borrow, 1)
                self.stdout.write(f"✅ Reminder sent to {borrow.user.username} for {borrow.book.title} (1 day)")

        for borrow in borrowings_today:
            existing = Notification.objects.filter(
                user=borrow.user,
                title__icontains="DUE TODAY",
                created_at__date=today
            ).exists()
            if not existing:
                notify_reminder(borrow, 0)
                self.stdout.write(f"✅ Reminder sent to {borrow.user.username} for {borrow.book.title} (due today)")

        for borrow in overdue_borrowings:
            existing = Notification.objects.filter(
                user=borrow.user,
                title__icontains="OVERDUE",
                created_at__date=today
            ).exists()
            if not existing:
                notify_overdue(borrow)
                self.stdout.write(f"✅ Overdue notification sent to {borrow.user.username} for {borrow.book.title}")

        self.stdout.write(self.style.SUCCESS(f"\n✅ All notifications sent successfully!"))